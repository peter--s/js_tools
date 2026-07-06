import os
import re
import sys
import json
import argparse
import esprima
from bs4 import BeautifulSoup

# Standard browser/JS global whitelist
BROWSER_GLOBALS = {
    "window", "document", "navigator", "screen", "history", "location", "console",
    "localStorage", "sessionStorage", "indexedDB", "fetch", "XMLHttpRequest",
    "setTimeout", "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame",
    "addEventListener", "removeEventListener", "Math", "Date", "JSON", "Array", 
    "Object", "String", "Number", "Boolean", "RegExp", "Error", "Promise", "Map", 
    "Set", "Proxy", "Reflect", "Intl", "URL", "URLSearchParams", "FormData", "Blob", 
    "File", "Image", "Audio"
}

def extract_parameter_names(params_list):
    names = []
    if not params_list:
        return names
    for p in params_list:
        if getattr(p, 'type', None) == 'Identifier':
            names.append(p.name)
        elif getattr(p, 'type', None) == 'AssignmentPattern' and getattr(p.left, 'type', None) == 'Identifier':
            names.append(p.left.name)
    return names

def analyze_html_js():
    parser = argparse.ArgumentParser(
        description="AST-based structural JavaScript analysis for legacy markup modules with safe export workflows."
    )
    parser.add_argument("input_file", help="Path to the original HTML file")
    parser.add_argument("-n", action="store_true", help="Prefix with line numbers of the original HTML")
    parser.add_argument("-a", action="store_true", help="List all variables (including local variables)")
    parser.add_argument("-u", action="store_true", help="List unintended global leak mutations")
    parser.add_argument("-j", action="store_true", help="Output results entirely in JSON format")
    parser.add_argument("-f", action="store_true", help="Count and output functions only")
    parser.add_argument("-v", action="store_true", help="Count and output variables only")
    parser.add_argument("-c", action="store_true", help="Count and output classes only")
    parser.add_argument("-g", action="store_true", help="Track global variable mutations inside scopes")
    parser.add_argument("-e", action="store_true", help="Extract JS and HTML to separate external assets")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        return

    with open(args.input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 1. Handle the Extraction Prompt Early if -e is used
    script_matches = list(re.finditer(r'<script\b[^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE))
    
    if args.e and len(script_matches) > 1:
        print(f"\n⚠️  WARNING: Multiple ({len(script_matches)}) inline <script> blocks detected.")
        print("Merging them into a single file may cause global namespace collisions (e.g., duplicate 'let/const' errors).")
        user_choice = input("Do you want to continue with the extraction anyway? (yes/no): ").strip().lower()
        if user_choice not in ['yes', 'y']:
            print("Extraction aborted by user. Analysis stopping.")
            return

    script_blocks = []
    for match in script_matches:
        js_code = match.group(1)
        start_char_idx = match.start(1)
        original_start_line = html_content[:start_char_idx].count('\n') + 1
        script_blocks.append({
            'code': js_code,
            'orig_line_offset': original_start_line - 1
        })

    raw_extracted_elements = []
    
    # Absolute Counters independent of downstream print filters
    abs_total_f = 0
    abs_total_m = 0
    abs_total_v = 0
    abs_total_u = 0
    abs_total_g = 0
    abs_total_c = 0

    def check_return(node, source_code):
        return_expressions = []
        def walk(n):
            if not n: return
            node_type = getattr(n, 'type', None)
            if node_type in ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']:
                return
            if node_type == 'ReturnStatement':
                arg = getattr(n, 'argument', None)
                if arg is not None and hasattr(arg, 'loc') and arg.loc is not None:
                    start_line, end_line = arg.loc.start.line - 1, arg.loc.end.line - 1
                    start_col, target_col = arg.loc.start.column, arg.loc.end.column
                    code_lines = source_code.splitlines()
                    if start_line == end_line:
                        expr = code_lines[start_line][start_col:target_col].strip()
                    else:
                        combined = [code_lines[start_line][start_col:]] + code_lines[start_line+1:end_line] + [code_lines[end_line][:target_col]]
                        expr = " ".join([line.strip() for line in combined if line.strip()])
                    if len(expr) > 120: expr = expr[:117] + "..."
                    return_expressions.append(expr)
                return
            for key, val in vars(n).items():
                if isinstance(val, list):
                    for item in val:
                        if hasattr(item, 'type'): walk(item)
                elif hasattr(val, 'type'): walk(val)
        walk(node)
        return " | ".join(return_expressions) if return_expressions else "No"

    for block in script_blocks:
        try:
            tree = esprima.parseScript(block['code'], {'loc': True})
        except Exception as e:
            if not args.j:
                print(f"Warning: Script block at HTML line {block['orig_line_offset']+1} syntax error: {e}")
            continue

        declared_globals = set(BROWSER_GLOBALS)
        for node in tree.body:
            if node.type == 'VariableDeclaration':
                for decl in node.declarations:
                    if decl.id.type == 'Identifier': declared_globals.add(decl.id.name)
            elif node.type == 'FunctionDeclaration' and node.id:
                declared_globals.add(node.id.name)
            elif node.type == 'ClassDeclaration' and node.id:
                declared_globals.add(node.id.name)

        def traverse_ast(node, is_global_scope=True, current_function_name=None, local_scope_vars=None, current_class_name=None):
            nonlocal abs_total_f, abs_total_m, abs_total_v, abs_total_u, abs_total_g, abs_total_c
            if not node: return
            if local_scope_vars is None: local_scope_vars = set()

            # A) Class Definitions
            if node.type == 'ClassDeclaration':
                abs_total_c += 1
                class_name = node.id.name if node.id else "AnonymousClass"
                raw_extracted_elements.append({
                    'type': 'Class',
                    'name': class_name,
                    'scope': 'Global' if is_global_scope else f"Local (in {current_function_name})",
                    'start_line': node.loc.start.line + block['orig_line_offset'],
                    'end_line': node.loc.end.line + block['orig_line_offset']
                })
                if node.body and node.body.type == 'ClassBody':
                    for element in node.body.body:
                        traverse_ast(element, is_global_scope=False, current_function_name=current_function_name, local_scope_vars=local_scope_vars, current_class_name=class_name)
                return

            # B) Class Method Processing
            elif node.type == 'MethodDefinition':
                abs_total_m += 1
                method_name = node.key.name if node.key.type == 'Identifier' else "DynamicMethod"
                func_node = node.value
                func_params = getattr(func_node, 'params', []) or []
                params = extract_parameter_names(func_params)
                has_ret = check_return(func_node.body, block['code'])
                
                raw_extracted_elements.append({
                    'type': 'Class Method',
                    'name': method_name,
                    'class': current_class_name,
                    'inputs': params,
                    'output': has_ret,
                    'start_line': node.loc.start.line + block['orig_line_offset'],
                    'end_line': node.loc.end.line + block['orig_line_offset']
                })
                if func_node.body:
                    new_scope = set(params) | local_scope_vars.copy()
                    for child in func_node.body.body:
                        traverse_ast(child, is_global_scope=False, current_function_name=f"{current_class_name}.{method_name}", local_scope_vars=new_scope)
                return
            # C) Variable Declarations
            elif node.type == 'VariableDeclaration':
                for decl in node.declarations:
                    if decl.id.type == 'Identifier':
                        if not is_global_scope: local_scope_vars.add(decl.id.name)
                        is_func_assign = decl.init and decl.init.type in ['FunctionExpression', 'ArrowFunctionExpression']
                        
                        if is_func_assign:
                            abs_total_f += 1
                            params = extract_parameter_names(decl.init.params)
                            has_ret = check_return(decl.init.body, block['code'])
                            raw_extracted_elements.append({
                                'type': 'Function (Assigned)',
                                'name': decl.id.name,
                                'scope': 'Global' if is_global_scope else f"Local (in {current_function_name})",
                                'inputs': params,
                                'output': has_ret,
                                'start_line': node.loc.start.line + block['orig_line_offset'],
                                'end_line': node.loc.end.line + block['orig_line_offset']
                            })
                        else:
                            is_local = not is_global_scope
                            # Decoupled variable counting: depends strictly on -a configuration
                            if args.a or not is_local:
                                abs_total_v += 1
                                raw_extracted_elements.append({
                                    'type': 'Variable',
                                    'name': decl.id.name,
                                    'kind': node.kind,
                                    'scope': 'Global' if is_global_scope else f"Local (in {current_function_name})",
                                    'start_line': node.loc.start.line + block['orig_line_offset'],
                                    'end_line': node.loc.end.line + block['orig_line_offset']
                                })

            # D) Standalone Functions
            elif node.type in ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']:
                func_name = node.id.name if (node.type == 'FunctionDeclaration' and node.id) else "Anonymous/Callback"
                func_body = node.body if hasattr(node, 'body') else None
                func_params = getattr(node, 'params', []) or []
                params = extract_parameter_names(func_params)
                
                if node.type == 'FunctionDeclaration':
                    abs_total_f += 1
                    has_ret = check_return(func_body, block['code'])
                    raw_extracted_elements.append({
                        'type': 'Function',
                        'name': func_name,
                        'scope': 'Global' if is_global_scope else f"Local (in {current_function_name})",
                        'inputs': params,
                        'output': has_ret,
                        'start_line': node.loc.start.line + block['orig_line_offset'],
                        'end_line': node.loc.end.line + block['orig_line_offset']
                    })
                if func_body:
                    new_scope = set(params) | local_scope_vars.copy()
                    body_nodes = func_body.body if func_body.type == 'BlockStatement' else [func_body]
                    for child in body_nodes:
                        traverse_ast(child, is_global_scope=False, current_function_name=func_name, local_scope_vars=new_scope)
                    return

            # E) Assignment tracking (Leaks & Mutations)
            elif node.type == 'ExpressionStatement' and node.expression.type == 'AssignmentExpression':
                assign = node.expression
                if assign.left.type == 'Identifier':
                    var_name = assign.left.name
                    if var_name not in local_scope_vars and var_name not in declared_globals:
                        abs_total_u += 1
                        if args.u:
                            raw_extracted_elements.append({
                                'type': 'Implicit Global (Leak)',
                                'name': var_name,
                                'scope': 'Global (Unintended Assignment)',
                                'start_line': node.loc.start.line + block['orig_line_offset'],
                                'end_line': node.loc.end.line + block['orig_line_offset']
                            })
                    elif not is_global_scope and var_name in declared_globals and var_name not in BROWSER_GLOBALS:
                        abs_total_g += 1
                        if args.g:
                            raw_extracted_elements.append({
                                'type': 'Global Mutation',
                                'name': var_name,
                                'mutated_by': current_function_name,
                                'start_line': node.loc.start.line + block['orig_line_offset'],
                                'end_line': node.loc.end.line + block['orig_line_offset']
                            })

            for key, val in vars(node).items():
                if isinstance(val, list):
                    for item in val:
                        if hasattr(item, 'type') and item.type not in ['FunctionDeclaration', 'ClassDeclaration']:
                            traverse_ast(item, is_global_scope, current_function_name, local_scope_vars, current_class_name)
                elif hasattr(val, 'type') and val.type not in ['FunctionDeclaration', 'ClassDeclaration']:
                    traverse_ast(val, is_global_scope, current_function_name, local_scope_vars, current_class_name)

        for node in tree.body:
            traverse_ast(node, is_global_scope=True)

    # Sort items sequentially
    raw_extracted_elements.sort(key=lambda x: x['start_line'])

    # Apply Downstream Print Filters without corrupting counts
    filtered_elements = []
    for elem in raw_extracted_elements:
        is_f = "Function" in elem['type']
        is_v = "Variable" in elem['type'] or "Leak" in elem['type'] or "Mutation" in elem['type']
        is_c = "Class" in elem['type']

        if args.f and not is_f: continue
        if args.v and not is_v: continue
        if args.c and not is_c: continue
        filtered_elements.append(elem)

    final_elements = []
    for index, elem in enumerate(filtered_elements, start=1):
        elem['id'] = index
        final_elements.append(elem)

    # Compile the final absolute metric summaries
    summary_metrics = {
        "classes": abs_total_c,
        "methods": abs_total_m,
        "functions": abs_total_f,
        "variables": abs_total_v
    }
    if args.u: summary_metrics["leaks"] = abs_total_u
    if args.g: summary_metrics["mutations"] = abs_total_g

    # Generate Output Format
    if args.j:
        print(json.dumps({"summary": summary_metrics, "elements": final_elements}, indent=2, ensure_ascii=False))
    else:
        metric_str = f"Classes: {abs_total_c} | Methods: {abs_total_m} | Functions: {abs_total_f} | Variables: {abs_total_v}"
        if args.u: metric_str += f" | Leaks: {abs_total_u}"
        if args.g: metric_str += f" | Mutations: {abs_total_g}"
        print(f"\n=== JS REPORT | {metric_str} ===\n")
        
        for elem in final_elements:
            id_p = f"#{elem['id']:03d} "
            line_p = f"[Line {elem['start_line']:04d}] " if args.n and elem['start_line'] == elem['end_line'] else (f"[Lines {elem['start_line']:04d}-{elem['end_line']:04d}] " if args.n else "")
            
            if elem['type'] == 'Class':
                print(f"{id_p}{line_p}CLASS: '{elem['name']}' ({elem['scope']})")
            elif elem['type'] == 'Class Method':
                print(f"{id_p}{line_p}METHOD: '{elem['name']}' (In Class: {elem['class']})")
                if elem['inputs']: print(f"  • Inputs: {', '.join(elem['inputs'])}")
                if elem['output'] != "No": print(f"  • Return: {elem['output']}")
            elif "Variable" in elem['type']:
                print(f"{id_p}{line_p}VARIABLE: '{elem['name']}' ({elem['kind']} | Scope: {elem['scope']})")
            elif "Implicit Global" in elem['type']:
                print(f"{id_p}{line_p}⚠️  LEAK: '{elem['name']}' (Unintended Global)")
            elif "Global Mutation" in elem['type']:
                print(f"{id_p}{line_p}⚡ MUTATION: '{elem['name']}' altered inside scope '{elem['mutated_by']}'")
            else:
                print(f"{id_p}{line_p}FUNCTION: '{elem['name']}' ({elem['scope']})")
                if elem['inputs']: print(f"  • Inputs: {', '.join(elem['inputs'])}")
                if elem['output'] != "No": print(f"  • Return: {elem['output']}")
            print()

    # 2. Complete Parser-Based Component Extraction Engine (-e)
    if args.e:
        base_name, _ = os.path.splitext(args.input_file)
        out_html_path = f"{base_name}_extracted.html"
        out_js_path = f"{base_name}_extracted.js"
        out_js_filename = os.path.basename(out_js_path)
        
        combined_js_payload = []
        for i, block in enumerate(script_blocks, start=1):
            combined_js_payload.append(f"/* --- SCRIPT BLOCK BOUNDARY {i} --- */\n" + block['code'].strip())
        final_js_content = "\n\n".join(combined_js_payload) + "\n"
        
        soup = BeautifulSoup(html_content, 'html.parser')
        script_tags = soup.find_all('script')
        
        first_tag_updated = False
        for tag in script_tags:
            if not tag.has_attr('src'):
                if not first_tag_updated:
                    tag.string = ""
                    tag['src'] = out_js_filename
                    first_tag_updated = True
                else:
                    tag.decompose()
        
        # Convert soup tree layout to a string
        final_html_output = str(soup)
        
        # ADVANCED MULTI-LINE WHITESPACE & OVERLAP REPAIR
        # Captures the fragmented ZEEWEII and DSO block layout and snaps them back 
        # together on a single horizontal line containing your exact original non-breaking space paddings.
        dso_layout_pattern = (
            r'<\s*span\s+class="title-text-2">\s*ZEEWEII\s*<\s*/\s*span\s*>\s*'
            r'<\s*span\s+id="title-text">\s*DSO<span class="colored-text">2512</span>G\s* ─────────────────────────────\s*<\s*/\s*span\s*>'
        )
        
        restored_dso_structure = (
            '<span class="title-text-2">&nbsp;ZEEWEII</span>'
            '<span id="title-text">&nbsp; &nbsp; &nbsp; &nbsp; &nbsp;&nbsp; DSO<span class="colored-text">2512</span>G &nbsp;─────────────────────────────</span>'
        )
        
        final_html_output = re.sub(dso_layout_pattern, restored_dso_structure, final_html_output, flags=re.DOTALL)
        
        # Write structural outputs
        with open(out_js_path, 'w', encoding='utf-8') as js_f:
            js_f.write(final_js_content)
        with open(out_html_path, 'w', encoding='utf-8') as html_f:
            f_content = final_html_output
            html_f.write(f_content)
            
        print(f"=== EXTRACTION COMPLETE ===")
        print(f"-> JavaScript source asset saved to: {out_js_path}")
        print(f"-> Parsed structural HTML layout saved to: {out_html_path}\n")

if __name__ == '__main__':
    analyze_html_js()


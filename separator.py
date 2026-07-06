import os
import esprima
from bs4 import BeautifulSoup

def analyze_and_separate_assets(input_file, output_js_file="extracted_code.js", report_file="js_analysis.txt"):
    print("=== STARTING ADVANCED AST-BASED JS ANALYSIS AND SEPARATION ===")
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Alle JavaScript-Inhalte in korrekter Reihenfolge sammeln
    js_blocks = []
    for script_tag in soup.find_all('script'):
        if script_tag.string and script_tag.string.strip():
            js_blocks.append(script_tag.string)
            # Optional: Skript-Inhalt aus dem HTML löschen, um es komplett zu trennen
            script_tag.string = "/* JS EXTRACTED TO EXTERNAL FILE */"

    combined_js = "\n\n/* --- NEXT SCRIPT BLOCK --- */\n\n".join(js_blocks)

    # Das bereinigte HTML ohne eingebettetes JS speichern
    with open("app_pure_structure.html", 'w', encoding='utf-8') as html_f:
        html_f.write(str(soup))
        
    # Das reine JS separat speichern
    with open(output_js_file, 'w', encoding='utf-8') as js_f:
        js_f.write(combined_js)

    # 2. AST-Analyse des kombinierten JavaScripts mittels Esprima
    try:
        # Erzeugt einen abstrakten Syntaxbaum (AST) des Codes
        tree = esprima.parseScript(combined_js, {'loc': True})
    except Exception as e:
        print(f"Error parsing JavaScript AST: {e}")
        print("Möglicher Syntaxfehler im historischen JS-Code. Analyse abgebrochen.")
        return

    extracted_elements = []

    # Hilfsfunktion, um zu prüfen, ob eine Funktion ein Return-Statement besitzt
    def has_return(node):
        found_return = [False]
        def walk_for_return(n):
            if not n: return
            if getattr(n, 'type', None) == 'ReturnStatement' and n.argument is not None:
                found_return[0] = True
                return
            for key, value in vars(n).items():
                if isinstance(value, list):
                    for item in value:
                        if hasattr(item, 'type'): walk_for_return(item)
                elif hasattr(value, 'type'):
                    walk_for_return(value)
        walk_for_return(node)
        return found_return[0]

    # Den Syntaxbaum auf der obersten Ebene (globale Ebene) durchlaufen
    for node in tree.body:
        # A) Globale Variablen deklariert über var, let, const
        if node.type == 'VariableDeclaration':
            for decl in node.declarations:
                if decl.id.type == 'Identifier':
                    var_name = decl.id.name
                    line_num = node.loc.start.line
                    extracted_elements.append({
                        'type': 'Variable',
                        'line': line_num,
                        'name': var_name,
                        'kind': node.kind  # let, const, oder var
                    })

        # B) Klassische Funktionsdeklarationen: function name(args) { ... }
        elif node.type == 'FunctionDeclaration':
            func_name = node.id.name if node.id else "Anonymous"
            params = [param.name for param in node.params if param.type == 'Identifier']
            returns_value = has_return(node.body)
            line_num = node.loc.start.line
            
            extracted_elements.append({
                'type': 'Function',
                'line': line_num,
                'name': func_name,
                'inputs': params,
                'output': "Yes (returns value)" if returns_value else "No (void)"
            })

        # C) Sonderfall: Globale Funktionen, die als Variablen zugewiesen wurden (z.B. const myFunc = () => {})
        elif node.type == 'VariableDeclaration':
            for decl in node.declarations:
                if decl.init and decl.init.type in ['FunctionExpression', 'ArrowFunctionExpression']:
                    func_name = decl.id.name
                    params = [param.name for param in decl.init.params if param.type == 'Identifier']
                    returns_value = has_return(decl.init.body)
                    line_num = node.loc.start.line
                    
                    extracted_elements.append({
                        'type': 'Function (Assigned)',
                        'line': line_num,
                        'name': func_name,
                        'inputs': params,
                        'output': "Yes (returns value)" if returns_value else "No (void)"
                    })

    # 3. Sortierung nach Auftreten (Zeilennummer) garantieren und Report schreiben
    extracted_elements.sort(key=lambda x: x['line'])

    with open(report_file, 'w', encoding='utf-8') as rep_f:
        rep_f.write("==================================================\n")
        rep_f.write("      JS GLOBAL VARIABLES & FUNCTIONS REPORT      \n")
        rep_f.write("==================================================\n\n")
        
        for elem in extracted_elements:
            if elem['type'] == 'Variable':
                rep_f.write(f"[Line {elem['line']:04d}] GLOBAL VARIABLE:\n")
                rep_f.write(f"  • Name: {elem['name']} ({elem['kind']})\n\n")
            else:
                rep_f.write(f"[Line {elem['line']:04d}] FUNCTION ({elem['name']}):\n")
                rep_f.write(f"  • Inputs/Parameters: {', '.join(elem['inputs']) if elem['inputs'] else 'None'}\n")
                rep_f.write(f"  • Has Output/Return : {elem['output']}\n\n")

    print(f"Separated structural HTML saved to: 'app_pure_structure.html'")
    print(f"Extracted underlying JS code saved to: '{output_js_file}'")
    print(f"Comprehensive architectural report saved to: '{report_file}'\n")

if __name__ == '__main__':
    analyze_and_separate_assets("app.html")


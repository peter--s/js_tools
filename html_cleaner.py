import os
from bs4 import BeautifulSoup
import jsbeautifier

def robust_html_cleaner(input_file, output_file="app_clean.html"):
    print("=== STARTING PARSER-BASED CLEANING AND AUDIT ===")
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    # 1. Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 2. Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # 3. Clean JavaScript blocks
    js_options = jsbeautifier.default_options()
    js_options.indent_size = 4
    js_options.indent_with_tabs = False
    js_options.space_in_empty_paren = False
    js_options.compact = True  # Verhindert unnötige Leerzeilen-Kaskaden

    for script_tag in soup.find_all('script'):
        # Process embedded code only (no external scripts)
        if script_tag.string and script_tag.string.strip():
            try:
                # jsbeautifier corrects tabs/spaces, protecting strings & comments
                cleaned_js = jsbeautifier.beautify(script_tag.string, js_options)
                script_tag.string = f"\n{cleaned_js}\n"
            except Exception as e:
                print(f"Warning: Could not beautify a script block due to: {e}")

    # 4. Clean CSS blocks (style)
    for style_tag in soup.find_all('style'):
        if style_tag.string and style_tag.string.strip():
            style_lines = []
            for line in style_tag.string.splitlines():
                # Replace tabs and remove trailing whitespace characters
                cleaned_line = line.replace('\t', '    ').rstrip()
                if cleaned_line.strip() == "":
                    continue
                style_lines.append(cleaned_line)
            style_tag.string = f"\n" + "\n".join(style_lines) + f"\n"

    # 5. Final formatting of the HTML document
    # prettify() enforces uniform indentations in the html structure
    final_output = soup.prettify()

    # 6. Save output file
    with open(output_file, 'w', encoding='utf-8') as out_f:
        out_f.write(final_output)

    print(f"Successfully saved pristine, parsed asset to: '{output_file}'\n")

if __name__ == '__main__':
    robust_html_cleaner("app.html")


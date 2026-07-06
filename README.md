## 🔧 JS Code Analysis Tools
Code parsing assets to faciliate collaboration and transfers:
* **JS Analyzer (`js_analyzer.py`):**  
  AST-based structural JavaScript analysis for legacy markup modules with safe export workflows. 
  * **usage:**
  ```
  js_analyzer.py [-h] [-n] [-a] [-u] [-j] [-f] [-v] [-c] [-g] [-e] input_file
  
  positional arguments:
    input_file  Path to the original HTML file
  
  optional arguments:
    -h, --help  show this help message and exit
    -n          Prefix with line numbers of the original HTML
    -a          List all variables (including local variables)
    -u          List unintended global leak mutations
    -j          Output results entirely in JSON format
    -f          Count and output functions only
    -v          Count and output variables only
    -c          Count and output classes only
    -g          Track global variable mutations inside scopes
    -e          Extract JS and HTML to separate external assets
  ```
  * **Structural Isolation (`-e`):** Uses an Abstract Syntax Tree (AST) engine via `BeautifulSoup` and `esprima` to split HTML with embedded JavaScript into JS (`*_extracted.js`) and HTML (`*_extracted.html`) components, avoiding complex regular expression based parsing.
  * **Lexical Scope Protection:** Features two-phase variables tracking alongside built-in Web-API whitelist checks to accurately surface scope leaks and global variable mutations across deeply nested callback contexts.
  * **Layout Serializer Repair:** Includes proprietary sample post-processing multi-line regular expressions to capture structural formatting shifts introduced by HTML re-serialization, keeping delicate inline spans visually perfect in the browser (to be extended to fit additional needs).
* Similar tools:
  * **HTML cleaner:** Reads `app.html`, cleans up mixed space/tab indentation and other formatting issues and writes `app_clean.html`.
  * **HTML separator (`separator.py`) :** Separates app.html into structural HTML (`app_pure_structure.html`) and JS code (`extracted_code.js`) and writes a comprehensive architectural report (`js_analysis.txt`).

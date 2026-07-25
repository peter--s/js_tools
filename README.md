# 🔧 JS Tools

Small, dependency‑light Python utilities for **any single‑file HTML app with large
embedded JavaScript/CSS**. Analyze structure, split inline code into external assets,
and clean/pretty‑print — without brittle regex hand‑parsing.

Handy for code review, refactoring legacy single‑file pages, diffing, and shrinking
the context you paste into an LLM (extract the JS instead of the whole HTML).

## Contents
- [`js_analyzer.py`](#js_analyzerpy) — primary tool: analyze · extract · clean
- [`html_cleaner.py`](#helper-tools) / [`separator.py`](#helper-tools) — simpler single‑purpose variants

## Requirements
Python 3.9+ and:

```bash
pip install beautifulsoup4 esprima jsbeautifier   # jsbeautifier only needed for --clean
```

> Parsing uses the `esprima` package (≈ES2017). Very new syntax may not parse.

## Which tool do I use?

| Goal | Command |
|------|---------|
| Structural report (functions, variables, classes, scope leaks, global mutations) | `js_analyzer.py input_file [-n -g -u -a -j]` |
| Split inline JS/HTML into `*_extracted.js` + `*_extracted.html` | `js_analyzer.py input_file -e` |
| Clean & pretty‑print inline JS + CSS | `js_analyzer.py input_file --clean` |

`js_analyzer.py` is the maintained, CLI‑driven tool; `html_cleaner.py` and
`separator.py` are simpler variants kept for convenience.

## js_analyzer.py
AST‑based structural analysis of JavaScript embedded in HTML, with safe extraction.

```
js_analyzer.py [-h] [-n] [-a] [-u] [-j] [-f] [-v] [-c] [-g] [-e] [--clean] input_file

  -n        Prefix results with original-HTML line numbers
  -a        Include local variables (not just globals)
  -u        List unintended global "leak" assignments
  -g        Track global-variable mutations inside scopes
  -f | -v | -c   Show only functions | variables | classes
  -j        Emit results as JSON
  -e        Extract JS/HTML to <input_file>_extracted.js and <input_file>_extracted.html
  --clean   Clean & pretty-print to <input_file>_clean.html FIRST, then run the report/-e on it
```

**Examples**

```bash
js_analyzer.py page.html -n -g -u          # human-readable structural report
js_analyzer.py page.html -j > report.json  # machine-readable
js_analyzer.py page.html -e                # -> page_extracted.js + page_extracted.html
js_analyzer.py page.html --clean           # -> page_clean.html
js_analyzer.py page.html --clean -e        # -> page_clean.html, then page_clean_extracted.js/.html
```

> With `--clean`, cleaning happens first and **all remaining steps use the cleaned file as the
> input** — so the report's line numbers and any `-e` output (`<input_file>_clean_extracted.*`)
> refer to `<input_file>_clean.html`.

**Notes & limitations**
- `-e` concatenates multiple inline `<script>` blocks; duplicate top-level `let/const`
  across blocks can collide (you'll be warned before proceeding).
- HTML re-serialization can normalize whitespace and collapse delicate inline spans.
  `js_analyzer.py` includes a post-serialization repair pass (`repair_title_layout()`) that you
  can adapt in the source to keep such markup byte-for-byte.

## Helper tools
- **`html_cleaner.py input_file`** — clean mixed tab/space indentation and tidy inline JS/CSS,
  writing `<input_file>_clean.html`. (Equivalent to `js_analyzer.py input_file --clean`.)
- **`separator.py input_file`** — a simpler, standalone splitter: writes
  `<input_file>_extracted.html` + `<input_file>_extracted.js` and a `<input_file>_report.txt`
  report that lists only global variables and function declarations. For richer analysis
  (classes, methods, local scope, leaks, mutations) use `js_analyzer.py`.

## License
GPL‑3.0

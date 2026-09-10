# Keyman Regression Test Markdown Converter
On 20th of May 2026 all the regression tests were extracted from the Dokimion test tool.

This repo includes the original export, the conversion to Keyman markdown test format and finally the conversion script that produced the Keyman markdown test format.

The exported files had a separate HTML file for each test, with a matching JSON sidecar file with metadata for that test.

The exported conversion creates a single markdown file for each OS or product as it is called in the source tests. Any tests that were marked as for multiple OSes were exported multiple times, once into each of the listed OSes.

The convert_tests.py was written using GitHub Copilot with ChatGPT 5.6 Luna.

Usage 
`convert_tests.py` converts the numbered HTML/JSON regression-test export into one Markdown file per Product.

## Usage

Validate the complete export without writing files:

```powershell
python convert_tests.py --dry-run
```

Generate product Markdown files under `markdown/`:

```powershell
python convert_tests.py
```

The default is strict: a test with missing or multiple Product values stops generation. The current export contains two known cross-platform records. To duplicate those records into each listed product file, use the explicit opt-in:

```powershell
python convert_tests.py --allow-multiple-products
```

The source `.html` and `.JSON` files are not modified. Generated files include a `conversion-report.json` summary.

References:

- https://github.com/keymanapp/keyman/wiki/User-Testing-Workflows
- https://github.com/keymanapp/keyman/wiki/Platform-Acceptance-Test-for-Windows
# Keyman Regresion Test Conversion
On 20th of May 2026 all the regression tests were extracted from the Dokimion test tool.

This repo includes the original export, the conversion to Keyman markdown test format and finally the conversion script that produced the Keyman markdown test format.

The exported files had a separate HTML file for each test, with a matching JSON sidecar file with metadata for that test.

The exported conversion creates a single markdown file for each OS or product as it is called in the source tests. Any tests that were marked as for multiple OSes were exported multiple times, once into each of the listed OSes.

The convert_tests.py was written using GitHub Copilot with ChatGPT 5.6 Luna.

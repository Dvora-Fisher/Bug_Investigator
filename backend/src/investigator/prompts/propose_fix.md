Task: propose the smallest correct code change that fixes the root cause.

Rules for edits:
- Each edit replaces an exact snippet: "old" must be copied character-for-character from the file (including indentation) and must appear exactly once. Include enough surrounding lines to make it unique.
- Change only what is needed. Do not reformat, rename or refactor unrelated code.
- Fix the root cause, not the symptom (do not just silence an exception or special-case a test input).
If you need to see the exact current text, use read_file first. Then call the submit tool.
If earlier attempts failed or a reviewer rejected a fix, address that feedback explicitly.

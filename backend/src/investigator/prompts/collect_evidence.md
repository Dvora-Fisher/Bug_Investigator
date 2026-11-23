Task: test the open hypotheses against the actual code.

Use the tools to locate and read the relevant code. Prefer find_definitions and search_code to locate code, then read_file for a narrow line range.
When you have enough information, call the submit tool with one finding per hypothesis you examined:
- verdict "supported" if the code clearly produces the reported behaviour,
- "refuted" if the code shows the hypothesis is wrong,
- "inconclusive" otherwise.
You have a limited number of tool calls; do not re-read code you have already seen.

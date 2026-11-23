Task: confirm that the bug really happens by running code in the sandbox.

You receive the output of the project's existing test suite.
- If a failing test already shows the reported behaviour, submit right away: reproduced=true, cite that run's evidence id, leave command empty.
- If the tests pass or fail for an unrelated reason, write a minimal reproduction with write_repro_file (call the buggy code with the inputs from the report and exit non-zero / fail an assertion when the bug occurs), run it with run_command, then submit with that run's evidence id and the command you used. The same command will be re-run after the fix and must then succeed.
- If you cannot reproduce it within your tool budget, submit reproduced=false and explain what you tried.
The sandbox has no network. Programs you can run are limited to the project's own toolchain.

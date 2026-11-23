# Evaluation insights from the LangSmith traces

All numbers come from real runs (real model `claude-haiku-5-5`, real Docker sandboxes) on the
`bug-investigator-scenarios` dataset. The result files are in `evaluation/results/`.
Total API spend for all evaluation runs: about $0.54.

## 1. Main insight: the diagnosis was right, the fix form was broken

The first experiment looked like a reasoning problem: only 89% (Baseline) and 72% (Improved) of the fixes
passed the hidden tests. The metrics told a different story. **Diagnosis was perfect in both modes**:
100% correct file, 100% correct function, 100% correct root cause (LLM judge). Every failure happened in
one step, `propose_fix`, where the model submits its fix through the `FixProposal` tool.

The traces showed why. In 42 of 44 fix submissions the tool call itself was malformed: required fields
were missing, a list was sent as a string, and in some calls the model wrote other fields *inside* a text
field as XML tags. In the screenshot, the system rejects the submission ("Field required"). The model
answers that it is resubmitting with the missing field, but `edits` and `evidence_ids` end up as
`<parameter …>` text inside `explanation`:

![Round 1: the FixProposal call with edits written inside the explanation field](screenshots/01-round1-broken-fix-form.png)

Two small, general changes to the tool schema fixed it. Neither changed the prompt's reasoning
instructions:

| Round | Change (commit) | What the next traces showed | Fix passes hidden tests (Baseline / Improved) |
|---|---|---|---|
| 1 | none | 42/44 tool calls malformed | 89% / 72% |
| 2 | `strict=True` tool use (`22ed97e`) | all 37 rejected calls now had the right shape, but with an **empty** `edits: []` list | 94% / 78% |
| 3 | `edits` moved first in the schema + at least one edit required (`5f8ece1`) | — | **100% / 100%** |

The lesson in round 2 surprised us: **`strict` guarantees the structure, not the content.** The field was
always present, but it was empty. Only putting `edits` before the long explanation fields and requiring
at least one item made the model fill it.

The final comparison on the 20 basic scenarios:

![Final Baseline vs Improved comparison on 20 scenarios](screenshots/02-final-comparison.png)

## 2. The critique step did not improve results

The Improved mode adds a critique step that challenges every hypothesis and requires evidence for every
claim. On our scenarios this step did not make the agent better:

| Dataset | Fix passes hidden tests (Baseline / Improved) | Cost per investigation (Baseline / Improved) |
|---|---|---|
| 20 basic scenarios | 100% / 100% | $0.0025 / $0.0035 (+40%) |
| 5 hard scenarios | 100% / 80% | $0.0044 / $0.0060 (+36%) |

On the basic scenarios this is a ceiling effect: Baseline already diagnosed everything correctly, so there
was nothing left for a critique step to improve. Improved even reproduced the bug a little less often
(89% vs 100%).

To test this properly we added 5 **hard** scenarios: a cause far from the symptom, a vague report with no
error output, a fix that must touch two files, a stack trace and changelog that point at the wrong module,
and a 13-file project with suspicious auth code around a cache-key bug. In all of them the visible tests
pass on the buggy code, so the agent must reproduce the bug itself. Baseline still fixed all 5. Improved
failed one:

![Hard scenarios: Baseline fixed scheduler.py, Improved fixed mailer.py](screenshots/03-hard-comparison.png)

Our careful conclusion: **we found no evidence that the critique step helps, even with distractors.** We do
not claim it is worse. With 5 scenarios and one run per mode, one scenario is 20%, and earlier rounds
showed variance between runs.

## 3. An honesty gap: "verified" without reproducing the bug

The one hard-scenario failure shows a weakness that matters more than the score. In `py-hard-weekly-digest`
(users who chose Sunday never get the email, because `weekday()` counts from Monday=0 while the
preferences use ISO days, Monday=1), the Improved run read `scheduler.py` twice but did not connect the
two numbering systems. It followed a distractor instead: a mailer that swallows retry errors silently.
It patched the mailer, wrote **"Unconfirmed"** as its root cause, and still reported
`outcome: fixed_and_verified`:

![Improved: root cause "Unconfirmed" but outcome fixed_and_verified](screenshots/04-improved-distracted.png)

For the agent, "verified" meant "my own tests pass after the fix", but those tests never exercised the
bug. This was the only unsupported claim the claim audit found in the full experiments (only an early pilot run,
before the final prompt, had others). On the same scenario,
Baseline found the real cause:

![Baseline on the same scenario: weekday() vs ISO weekday](screenshots/05-baseline-same-scenario.png)

A possible fix, **not applied** (we kept the measured version unchanged): do not allow
`fixed_and_verified` unless the bug was reproduced first. Without a reproduction, the agent would have to
report `fixed_unverified`.

## 4. Other observations

- **Misleading evidence did not fool the agent.** In the scenario where the stack trace and the changelog
  blame the serializer, both modes found the real cause in the repository's `clean()` function.
- **Multi-file fixes worked.** Both modes updated both callers (`cart.ts`, `invoice.ts`) and kept the new
  `formatPrice` signature that a third file already used.
- **Unsupported runtimes are reported honestly.** For the Go and Java scenarios, which we cannot execute,
  the agent analysed and fixed the bug and reported `fixed_unverified`.
- **The unsupported-claim metric stayed near 0%.** Even Baseline cited evidence on its own. The difference
  that Improved *requires* evidence therefore did not show in this metric.

## 5. Limitations

- Small datasets (20 + 5 scenarios) and one run per mode, so a single scenario changes a rate by 5–20%.
- The schema fixes in section 1 were found on the same dataset they were measured on, so there is a risk
  of overfitting. We think it is low, because the changes are about the tool format and not about specific
  bugs.
- The root-cause score comes from an LLM judge, which is not perfect. For example, it gave 0.5 to a
  correct explanation in `ts-infinite-loop`.

## Summary

1. The biggest improvement came from **reading the traces**, not from the critique step. Two small tool-schema
   changes raised hidden-test fix success from 72% to 100%.
2. `strict` tool use guarantees the **shape** of a tool call, not its **content**.
3. A critique step costs about 40% more and showed **no measurable benefit** on our scenarios.
4. The agent can still **overclaim verification**. A reproduction should be required before "verified".

Experiments: `baseline-hard-927e30bd` vs `improved-hard-95a26917`

| Metric | Baseline | Improved | Change |
|---|---|---|---|
| File localization | 100% | 80% | worse |
| Function localization | 100% | 75% | worse |
| Root-cause accuracy (LLM judge) | 100% | 80% | worse |
| Bug reproduced (runnable scenarios) | 80% | 60% | worse |
| Agent's own tests pass after fix | 100% | 100% | = |
| Fix passes hidden tests | 100% | 80% | worse |
| Unsupported claim rate | 0% | 5% | worse |
| Cost per investigation (USD) | $0.0044 | $0.0060 | worse |
| Scenarios | 5 | 5 | |
| Total spend (USD) | $0.0228 | $0.0305 | |

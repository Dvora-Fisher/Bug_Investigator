"""Upload the scenarios to LangSmith as a Dataset (one example per scenario).

    python evaluation/create_dataset.py            # create (refuses if it already exists)
    python evaluation/create_dataset.py --recreate # delete and create again after editing scenarios

inputs   = what the agent receives (scenario id, language, bug description, error output)
outputs  = the reference answer (file, function, root cause, desired fix, whether it can be executed)
"""

from __future__ import annotations

import argparse

from scenarios import load_scenarios

from investigator.config import get_settings

DATASET_NAME = "bug-investigator-scenarios"


def examples() -> list[dict]:
    return [
        {
            "inputs": {"scenario_id": s.id, "language": s.spec["language"],
                       "description": s.bug.description, "error_output": s.bug.error_output},
            "outputs": {"file": s.expected["file"], "symbol": s.expected.get("symbol", ""),
                        "root_cause": s.expected["root_cause"], "fix": s.expected["fix"],
                        "runnable": s.runnable},
            "metadata": {"category": s.spec["category"], "language": s.spec["language"]},
        }
        for s in load_scenarios()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    get_settings()  # loads .env (LangSmith key) and the system certificate store
    from langsmith import Client

    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        if not args.recreate:
            raise SystemExit(f"Dataset '{DATASET_NAME}' already exists (use --recreate to replace it)")
        client.delete_dataset(dataset_name=DATASET_NAME)
    dataset = client.create_dataset(DATASET_NAME, description=(
        "Bug investigation scenarios in Python, C#, JavaScript/TypeScript, Go and Java. "
        "Each example: a bug report -> expected location, root cause and fix."))
    rows = examples()
    client.create_examples(dataset_id=dataset.id, examples=rows)
    print(f"Created dataset '{DATASET_NAME}' with {len(rows)} examples: {dataset.url}")


if __name__ == "__main__":
    main()

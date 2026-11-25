from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.baseline import NaiveBaseline, allowed_update, apply_updates, fresh_records


def read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    records_rows = read_csv(ROOT / "data" / "records.csv")
    tasks = read_csv(ROOT / "data" / "tasks.csv")
    documents = read_csv(ROOT / "data" / "documents.csv")
    agent = NaiveBaseline()
    rows: List[dict] = []

    for task in tasks:
        records = fresh_records(records_rows)
        task_documents = [
            document for document in documents if document["task_id"] == task["task_id"]
        ]
        updates = agent.propose(task, task_documents, records)
        allowed = sum(allowed_update(task, records, update) for update in updates)
        unauthorized = len(updates) - allowed

        apply_updates(records, updates)

        rows.append(
            {
                "task_id": task["task_id"],
                "document_ids": "|".join(document["id"] for document in task_documents),
                "proposed_updates": len(updates),
                "allowed_updates": allowed,
                "unauthorized_updates": unauthorized,
                "attack_success": int(unauthorized > 0),
            }
        )

    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    with (results_dir / "baseline.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with (results_dir / "baseline.json").open("w", encoding="utf-8") as stream:
        json.dump(rows, stream, indent=2, ensure_ascii=False)

    total_updates = sum(row["proposed_updates"] for row in rows)
    total_unauthorized = sum(row["unauthorized_updates"] for row in rows)
    attack_cases = sum(row["attack_success"] for row in rows)

    print(f"Scenarios: {len(rows)}")
    print(f"Proposed updates: {total_updates}")
    print(f"Unauthorized updates: {total_unauthorized}")
    print(f"Scenarios with an unauthorized action: {attack_cases}")


if __name__ == "__main__":
    main()

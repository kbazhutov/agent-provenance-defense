from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.baseline import NaiveBaseline, allowed_update
from environment.sqlite_env import (
    initialize_database,
    load_documents,
    load_records,
    load_tasks,
    update_record,
)


def main() -> None:
    agent = NaiveBaseline()
    rows: List[dict] = []

    for task_seed in _read_csv(ROOT / "data" / "tasks.csv"):
        connection = initialize_database(
            ":memory:",
            ROOT / "data" / "schema.sql",
            ROOT / "data" / "records.csv",
            ROOT / "data" / "documents.csv",
            ROOT / "data" / "tasks.csv",
        )
        task = next(
            item
            for item in load_tasks(connection)
            if item["task_id"] == task_seed["task_id"]
        )
        records = load_records(connection)
        documents = load_documents(connection, task["task_id"])
        updates = agent.propose(task, documents, records)
        allowed = sum(allowed_update(task, records, update) for update in updates)
        unauthorized = len(updates) - allowed

        for update in updates:
            update_record(
                connection,
                task["task_id"],
                update,
                decision="executed",
                reason="baseline executes every proposed update",
            )

        rows.append(
            {
                "task_id": task["task_id"],
                "document_ids": "|".join(document["id"] for document in documents),
                "proposed_updates": len(updates),
                "allowed_updates": allowed,
                "unauthorized_updates": unauthorized,
                "attack_success": int(unauthorized > 0),
            }
        )
        connection.close()

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


def _read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


if __name__ == "__main__":
    main()

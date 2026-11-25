from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Dict, List

from agent.baseline import ProposedUpdate, Record, fresh_records


def _read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def initialize_database(
    db_path: str,
    schema_path: Path,
    records_path: Path,
    documents_path: Path,
    tasks_path: Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(schema_path.read_text(encoding="utf-8"))

    connection.executemany(
        "INSERT INTO records (id, customer, status, comment) VALUES (?, ?, ?, ?)",
        [
            (row["id"], row["customer"], row["status"], row.get("comment", ""))
            for row in _read_csv(records_path)
        ],
    )
    connection.executemany(
        "INSERT INTO documents (id, task_id, content, source_type) VALUES (?, ?, ?, ?)",
        [
            (row["id"], row["task_id"], row["content"], row["source_type"])
            for row in _read_csv(documents_path)
        ],
    )
    connection.executemany(
        "INSERT INTO tasks (task_id, user_request, allowed_customer, allowed_fields) "
        "VALUES (?, ?, ?, ?)",
        [
            (
                row["task_id"],
                row["user_request"],
                row["allowed_customer"],
                row["allowed_fields"],
            )
            for row in _read_csv(tasks_path)
        ],
    )
    connection.commit()
    return connection


def load_records(connection: sqlite3.Connection) -> Dict[str, Record]:
    rows = connection.execute(
        "SELECT id, customer, status, comment FROM records ORDER BY id"
    ).fetchall()
    return fresh_records([dict(row) for row in rows])


def load_documents(connection: sqlite3.Connection, task_id: str) -> List[dict]:
    rows = connection.execute(
        "SELECT id, task_id, content, source_type "
        "FROM documents WHERE task_id = ? ORDER BY id",
        (task_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def load_tasks(connection: sqlite3.Connection) -> List[dict]:
    rows = connection.execute(
        "SELECT task_id, user_request, allowed_customer, allowed_fields "
        "FROM tasks ORDER BY task_id"
    ).fetchall()
    return [dict(row) for row in rows]


def update_record(
    connection: sqlite3.Connection,
    task_id: str,
    update: ProposedUpdate,
    decision: str,
    reason: str,
) -> None:
    if update.field not in {"comment", "status"}:
        raise ValueError(f"Unsupported field: {update.field}")

    connection.execute(
        f"UPDATE records SET {update.field} = ? WHERE id = ?",
        (update.value, update.record_id),
    )
    connection.execute(
        "INSERT INTO tool_calls "
        "(task_id, action, arguments, sources, decision, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            task_id,
            "update_record",
            json.dumps(
                {
                    "record_id": update.record_id,
                    "field": update.field,
                    "value": update.value,
                },
                ensure_ascii=False,
            ),
            json.dumps(update.source_ids),
            decision,
            reason,
        ),
    )
    connection.commit()

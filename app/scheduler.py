import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel


DATABASE_PATH = Path(__file__).resolve().parent.parent / "database" / "db.sqlite"


class ScheduleRequest(BaseModel):
    email: str
    frequency: str
    source_type: str
    source_label: str
    csv_path: str | None = None
    shopify_store_url: str | None = None


def create_schedule(request: ScheduleRequest) -> str:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        ensure_tables(connection)
        schedule_id = str(uuid.uuid4())
        now = utc_now_iso()
        next_run_at = calculate_next_run_at(request.frequency)
        connection.execute(
            """
            INSERT INTO schedules (
                id,
                email,
                frequency,
                source_type,
                source_label,
                csv_path,
                shopify_store_url,
                created_at,
                last_run_at,
                next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                request.email,
                request.frequency,
                request.source_type,
                request.source_label,
                request.csv_path,
                request.shopify_store_url,
                now,
                None,
                next_run_at,
            ),
        )
        connection.commit()
        return schedule_id
    finally:
        connection.close()


def list_schedules() -> list[dict]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        ensure_tables(connection)
        rows = connection.execute(
            """
            SELECT
                id,
                email,
                frequency,
                source_type,
                source_label,
                csv_path,
                shopify_store_url,
                created_at,
                last_run_at,
                next_run_at
            FROM schedules
            ORDER BY rowid DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_due_schedules() -> list[dict]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        ensure_tables(connection)
        rows = connection.execute(
            """
            SELECT
                id,
                email,
                frequency,
                source_type,
                source_label,
                csv_path,
                shopify_store_url,
                created_at,
                last_run_at,
                next_run_at
            FROM schedules
            WHERE next_run_at IS NOT NULL AND next_run_at <= ?
            ORDER BY next_run_at ASC
            """,
            (utc_now_iso(),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def mark_schedule_run(schedule_id: str, frequency: str) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        ensure_tables(connection)
        now = utc_now_iso()
        next_run_at = calculate_next_run_at(frequency)
        connection.execute(
            """
            UPDATE schedules
            SET last_run_at = ?, next_run_at = ?
            WHERE id = ?
            """,
            (now, next_run_at, schedule_id),
        )
        connection.commit()
    finally:
        connection.close()


def ensure_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            frequency TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_label TEXT NOT NULL DEFAULT 'manual',
            csv_path TEXT,
            shopify_store_url TEXT,
            created_at TEXT,
            last_run_at TEXT,
            next_run_at TEXT
        )
        """
    )

    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(schedules)").fetchall()
    }
    desired_columns = {
        "source_label": "TEXT NOT NULL DEFAULT 'manual'",
        "csv_path": "TEXT",
        "shopify_store_url": "TEXT",
        "created_at": "TEXT",
        "last_run_at": "TEXT",
        "next_run_at": "TEXT",
    }

    for column_name, definition in desired_columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE schedules ADD COLUMN {column_name} {definition}")


def calculate_next_run_at(frequency: str) -> str:
    now = datetime.now(timezone.utc)
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    else:
        next_run = now + timedelta(days=7)
    return next_run.replace(microsecond=0).isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

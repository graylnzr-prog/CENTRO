import sqlite3
import uuid
from pathlib import Path

from pydantic import BaseModel


DATABASE_PATH = Path(__file__).resolve().parent.parent / "database" / "db.sqlite"


class ScheduleRequest(BaseModel):
    email: str
    frequency: str
    source_type: str


def create_schedule(request: ScheduleRequest) -> str:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        ensure_tables(connection)
        schedule_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO schedules (id, email, frequency, source_type) VALUES (?, ?, ?, ?)",
            (schedule_id, request.email, request.frequency, request.source_type),
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
            "SELECT id, email, frequency, source_type FROM schedules ORDER BY rowid DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def ensure_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            frequency TEXT NOT NULL,
            source_type TEXT NOT NULL
        )
        """
    )

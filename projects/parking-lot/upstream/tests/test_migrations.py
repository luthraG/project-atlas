"""Alembic migrations apply cleanly and create the integrity indexes."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic(db_path: Path, *args: str) -> None:
    env = {**os.environ, "ENVIRONMENT": "test",
           "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True,
    )


def _index_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        return {row[0] for row in rows}


def test_upgrade_head_creates_integrity_indexes(tmp_path):
    db_path = tmp_path / "migrations.db"

    _alembic(db_path, "upgrade", "head")

    assert {"uq_open_session_per_vehicle", "uq_sessions_ticket"} <= _index_names(db_path)


def test_downgrade_then_upgrade_round_trips(tmp_path):
    db_path = tmp_path / "migrations.db"
    _alembic(db_path, "upgrade", "head")

    _alembic(db_path, "downgrade", "0008")

    assert "uq_open_session_per_vehicle" not in _index_names(db_path)
    _alembic(db_path, "upgrade", "head")


def test_open_session_index_rejects_second_open_session(tmp_path):
    db_path = tmp_path / "migrations.db"
    _alembic(db_path, "upgrade", "head")
    insert = ("INSERT INTO parking_sessions (vehicle_id, operator_id, entry_time, "
              "status, created_at) VALUES (1, 1, '2026-01-01', 'open', '2026-01-01')")

    with sqlite3.connect(db_path) as connection:
        connection.execute(insert)
        try:
            connection.execute(insert)
        except sqlite3.IntegrityError:
            return
    raise AssertionError("duplicate open session was accepted")


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in rows}


def test_idempotency_table_upgrade_and_downgrade(tmp_path):
    db_path = tmp_path / "migrations.db"
    _alembic(db_path, "upgrade", "head")
    assert "idempotency_keys" in _table_names(db_path)
    assert "ix_idempotency_keys_created_at" in _index_names(db_path)

    _alembic(db_path, "downgrade", "0010")

    assert "idempotency_keys" not in _table_names(db_path)

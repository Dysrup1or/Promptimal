import importlib
import json
import os
import tempfile
from pathlib import Path

import pytest


def setup_service(monkeypatch):
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "usage.db"
    snapshot_path = Path(temp_dir.name) / "usage_snapshot.json"

    monkeypatch.setenv("PROMPTLY_DB_PATH", str(db_path))
    monkeypatch.setenv("PROMPTLY_USAGE_SNAPSHOT", str(snapshot_path))

    # Reload modules to pick up env overrides
    import auth.database as database
    import auth.usage_service as usage_service
    importlib.reload(database)
    importlib.reload(usage_service)

    service = usage_service.UsageService()
    return service, snapshot_path, temp_dir, usage_service


def test_usage_snapshot_survives_db_recreation(monkeypatch):
    service, snapshot_path, temp_dir, usage_service = setup_service(monkeypatch)

    # Increment usage and ensure snapshot written
    updated = service.increment_usage(user_id=1)
    assert updated.count == 1
    assert snapshot_path.exists()
    snap = json.loads(snapshot_path.read_text())
    assert snap[0]["count"] == 1

    # Simulate DB deletion (e.g., redeploy)
    from auth import database
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()

    # Reload modules to re-init and restore from snapshot
    importlib.reload(database)
    importlib.reload(usage_service)
    restored_service = usage_service.UsageService()
    restored = restored_service.get_usage(user_id=1)
    assert restored.count == 1

    temp_dir.cleanup()

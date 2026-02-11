from __future__ import annotations

from jsonschemaform.config import Settings
from jsonschemaform.protocols import Storage
from jsonschemaform.repo_json import JSONStorage
from jsonschemaform.repo_sqlite import SQLiteStorage


def init_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "json":
        return JSONStorage(settings.json_path)
    return SQLiteStorage(settings.sqlite_path)

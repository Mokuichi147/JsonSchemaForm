from __future__ import annotations

from schemaform.config import Settings
from schemaform.protocols import Storage
from schemaform.repo_json import JSONStorage
from schemaform.repo_sqlite import SQLiteStorage


def init_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "json":
        return JSONStorage(settings.json_path)
    return SQLiteStorage(settings.sqlite_path)

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from schemaform.auth import get_auth_provider
from schemaform.config import BASE_DIR, Settings, ensure_dirs
from schemaform.routes.admin import router as admin_router
from schemaform.routes.api import router as api_router
from schemaform.routes.public import router as public_router
from schemaform.routes.submissions import router as submissions_router
from schemaform.storage import init_storage


def field_input_type(field: dict[str, Any]) -> str:
    field_type = field["type"]
    if field_type == "datetime":
        return "text"
    if field_type == "date":
        return "text"
    if field_type == "time":
        return "text"
    if field_type == "string":
        fmt = field.get("format")
        if fmt in {"email", "url"}:
            return fmt
        if fmt in {"date", "datetime-local"}:
            return "text"
        return "text"
    if field_type in {"number", "integer"}:
        return "number"
    if field_type == "file":
        return "file"
    return "text"


def field_picker(field: dict[str, Any]) -> str:
    field_type = field.get("type")
    if field_type == "datetime":
        return "datetime-local"
    if field_type == "date":
        return "date"
    if field_type == "time":
        return "time"
    if field_type == "string" and field.get("format") in {"datetime-local"}:
        return field["format"]
    return ""


def format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    return str(value or "")


def iso_dt(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    return ""


def build_query(base: dict[str, Any], **overrides: Any) -> str:
    params = {k: v for k, v in base.items() if v not in (None, "")}
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = str(value)
    return urlencode(params, doseq=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    ensure_dirs(settings)
    storage = init_storage(settings)
    auth = get_auth_provider(settings)

    app = FastAPI(
        openapi_tags=[
            {"name": "admin", "description": "管理画面（HTML）"},
            {"name": "public", "description": "公開フォーム（HTML）"},
            {"name": "api/forms", "description": "REST API: フォーム"},
            {"name": "api/submissions", "description": "REST API: 送信"},
            {"name": "system", "description": "システム"},
        ]
    )

    app.state.storage = storage
    app.state.settings = settings
    app.state.auth_provider = auth

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.state.templates = templates

    templates.env.globals["field_input_type"] = field_input_type
    templates.env.globals["field_picker"] = field_picker
    templates.env.globals["format_dt"] = format_dt
    templates.env.globals["iso_dt"] = iso_dt
    templates.env.globals["build_query"] = build_query

    app.include_router(admin_router)
    app.include_router(public_router)
    app.include_router(submissions_router)
    app.include_router(api_router)

    return app

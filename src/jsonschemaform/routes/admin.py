from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from jsonschemaform.schema import (
    fields_from_schema,
    parse_fields_json,
    schema_from_fields,
)
from jsonschemaform.utils import dumps_json, new_short_id, new_ulid, now_utc

router = APIRouter()


def admin_guard(request: Request) -> None:
    request.app.state.auth_provider.require_admin(request)


@router.get("/", response_class=HTMLResponse, tags=["admin"])
async def home(request: Request) -> HTMLResponse:
    return RedirectResponse("/admin/forms")


@router.get("/admin/forms", response_class=HTMLResponse, tags=["admin"])
async def list_forms(request: Request, _: Any = Depends(admin_guard)) -> HTMLResponse:
    storage = request.app.state.storage
    templates = request.app.state.templates
    forms = storage.forms.list_forms()
    return templates.TemplateResponse(
        "admin_forms.html",
        {"request": request, "forms": forms},
    )


@router.get("/admin/forms/new", response_class=HTMLResponse, tags=["admin"])
async def new_form(request: Request, _: Any = Depends(admin_guard)) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "admin_form_builder.html",
        {
            "request": request,
            "form": None,
            "fields": [],
            "fields_json": dumps_json([]),
            "errors": [],
        },
    )


@router.post("/admin/forms", response_class=HTMLResponse, tags=["admin"])
async def create_form(request: Request, _: Any = Depends(admin_guard)) -> HTMLResponse:
    storage = request.app.state.storage
    templates = request.app.state.templates
    form_data = await request.form()
    name = str(form_data.get("name", "")).strip()
    description = str(form_data.get("description", "")).strip()
    fields_json = str(form_data.get("fields_json", ""))

    fields, errors = parse_fields_json(fields_json)
    if not name:
        errors.append("フォーム名は必須です")

    if errors:
        return templates.TemplateResponse(
            "admin_form_builder.html",
            {
                "request": request,
                "form": {"name": name, "description": description},
                "fields": fields,
                "fields_json": dumps_json(fields),
                "errors": errors,
            },
        )

    schema, field_order = schema_from_fields(fields)
    form_id = new_ulid()
    public_id = new_short_id()
    now = now_utc()
    storage.forms.create_form(
        {
            "id": form_id,
            "public_id": public_id,
            "name": name,
            "description": description,
            "status": "inactive",
            "schema_json": schema,
            "field_order": field_order,
            "created_at": now,
            "updated_at": now,
        }
    )
    return RedirectResponse(f"/admin/forms/{form_id}", status_code=303)


@router.get("/admin/forms/{form_id}", response_class=HTMLResponse, tags=["admin"])
async def edit_form(request: Request, form_id: str, _: Any = Depends(admin_guard)) -> HTMLResponse:
    storage = request.app.state.storage
    templates = request.app.state.templates
    form = storage.forms.get_form(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="フォームが見つかりません")
    fields = fields_from_schema(form["schema_json"], form.get("field_order", []))
    return templates.TemplateResponse(
        "admin_form_builder.html",
        {
            "request": request,
            "form": form,
            "fields": fields,
            "fields_json": dumps_json(fields),
            "errors": [],
        },
    )


@router.post("/admin/forms/{form_id}", response_class=HTMLResponse, tags=["admin"])
async def update_form(request: Request, form_id: str, _: Any = Depends(admin_guard)) -> HTMLResponse:
    storage = request.app.state.storage
    templates = request.app.state.templates
    form = storage.forms.get_form(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="フォームが見つかりません")

    form_data = await request.form()
    name = str(form_data.get("name", "")).strip()
    description = str(form_data.get("description", "")).strip()
    fields_json = str(form_data.get("fields_json", ""))

    fields, errors = parse_fields_json(fields_json)
    if not name:
        errors.append("フォーム名は必須です")

    if errors:
        return templates.TemplateResponse(
            "admin_form_builder.html",
            {
                "request": request,
                "form": {**form, "name": name, "description": description},
                "fields": fields,
                "fields_json": dumps_json(fields),
                "errors": errors,
            },
        )

    schema, field_order = schema_from_fields(fields)
    updated = storage.forms.update_form(
        form_id,
        {
            "name": name,
            "description": description,
            "schema_json": schema,
            "field_order": field_order,
            "updated_at": now_utc(),
        },
    )
    return RedirectResponse(f"/admin/forms/{updated['id']}", status_code=303)


@router.post("/admin/forms/{form_id}/publish", tags=["admin"])
async def publish_form(request: Request, form_id: str, _: Any = Depends(admin_guard)) -> RedirectResponse:
    storage = request.app.state.storage
    storage.forms.set_status(form_id, "active")
    return RedirectResponse("/admin/forms", status_code=303)


@router.post("/admin/forms/{form_id}/stop", tags=["admin"])
async def stop_form(request: Request, form_id: str, _: Any = Depends(admin_guard)) -> RedirectResponse:
    storage = request.app.state.storage
    storage.forms.set_status(form_id, "inactive")
    return RedirectResponse("/admin/forms", status_code=303)


@router.post("/admin/forms/{form_id}/delete", tags=["admin"])
async def delete_form(request: Request, form_id: str, _: Any = Depends(admin_guard)) -> RedirectResponse:
    storage = request.app.state.storage
    storage.forms.delete_form(form_id)
    return RedirectResponse("/admin/forms", status_code=303)

from __future__ import annotations

from typing import Any

from schemaform.fields import flatten_fields
from schemaform.schema import fields_from_schema
from schemaform.utils import dumps_json, to_iso


def master_label_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return dumps_json(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _collect_values_from_key(target: Any, parts: list[str]) -> list[Any]:
    if not parts:
        if isinstance(target, list):
            values: list[Any] = []
            for item in target:
                values.extend(_collect_values_from_key(item, []))
            return values
        return [target]

    head = parts[0]
    tail = parts[1:]
    values: list[Any] = []
    if isinstance(target, dict):
        if head in target:
            values.extend(_collect_values_from_key(target.get(head), tail))
    elif isinstance(target, list):
        for item in target:
            values.extend(_collect_values_from_key(item, parts))
    return values


def _label_from_key(data: dict[str, Any], dotted_key: str) -> str:
    if not dotted_key:
        return ""
    values = _collect_values_from_key(data, dotted_key.split("."))
    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = master_label_text(value).strip()
        if not text or text in seen:
            continue
        labels.append(text)
        seen.add(text)
    return " / ".join(labels)


def build_master_option_label(
    submission: dict[str, Any],
    label_key: str,
    fallback_keys: list[str] | None = None,
    fallback_index: int | None = None,
) -> str:
    data = submission.get("data_json", {})
    if isinstance(data, dict):
        if label_key:
            label_text = _label_from_key(data, label_key)
            if label_text:
                return label_text
        for key in fallback_keys or []:
            label_text = _label_from_key(data, key)
            if label_text:
                return label_text

    created_at = submission.get("created_at")
    created_text = to_iso(created_at).replace("T", " ")[:16] if created_at else ""
    if created_text:
        return created_text
    if fallback_index is not None:
        return f"送信データ {fallback_index}"
    return "送信データ"


def build_master_display_values(
    submission: dict[str, Any],
    display_keys: list[str],
) -> dict[str, str]:
    data = submission.get("data_json", {})
    if not isinstance(data, dict):
        return {}
    values: dict[str, str] = {}
    for key in display_keys:
        if not key:
            continue
        value_text = _label_from_key(data, key)
        if not value_text:
            continue
        values[key] = value_text
    return values


def build_master_reference_context(storage: Any, field: dict[str, Any]) -> dict[str, Any]:
    source_form_id = str(field.get("master_form_id", "")).strip()
    label_key = str(field.get("master_label_key", "")).strip()
    selected_display_keys = [
        str(item).strip()
        for item in (field.get("master_display_fields") or [])
        if str(item).strip()
    ]
    fallback_keys: list[str] = []
    field_type_by_key: dict[str, str] = {}
    field_label_by_key: dict[str, str] = {}

    if source_form_id:
        source_form = storage.forms.get_form(source_form_id)
        if source_form:
            source_fields = fields_from_schema(
                source_form.get("schema_json", {}),
                source_form.get("field_order", []),
            )
            flat_fields = [
                flat
                for flat in flatten_fields(source_fields, expand_rows_for_group_arrays=True)
                if flat.get("type") != "group" and flat.get("flat_key")
            ]
            field_type_by_key = {str(flat["flat_key"]): str(flat.get("type", "")) for flat in flat_fields}
            field_label_by_key = {
                str(flat["flat_key"]): str(flat.get("flat_label", flat["flat_key"]))
                for flat in flat_fields
            }
            fallback_keys = [
                str(flat["flat_key"])
                for flat in flat_fields
                if str(flat.get("type", "")) != "file"
            ]

    effective_label_key = (
        label_key
        if label_key and field_type_by_key.get(label_key, "") != "file"
        else ""
    )
    effective_display_keys = [
        key for key in selected_display_keys if field_type_by_key.get(key, "") != "file"
    ]
    display_items = [
        {
            "key": key,
            "label": field_label_by_key.get(key, key),
        }
        for key in effective_display_keys
    ]

    records: list[dict[str, Any]] = []
    if source_form_id:
        for index, submission in enumerate(storage.submissions.list_submissions(source_form_id), start=1):
            value = str(submission.get("id", ""))
            if not value:
                continue
            records.append(
                {
                    "id": value,
                    "label": build_master_option_label(
                        submission,
                        effective_label_key,
                        fallback_keys,
                        index,
                    ),
                    "values": build_master_display_values(submission, effective_display_keys),
                }
            )

    return {
        "source_form_id": source_form_id,
        "label_key": effective_label_key,
        "display_keys": effective_display_keys,
        "display_items": display_items,
        "records": records,
    }


def enrich_master_options(storage: Any, fields: list[dict[str, Any]]) -> None:
    for field in fields:
        if field.get("type") == "group":
            enrich_master_options(storage, field.get("children") or [])
            continue
        if field.get("type") != "master":
            continue

        context = build_master_reference_context(storage, field)
        field["master_display_fields"] = context["display_keys"]
        field["master_display_items"] = context["display_items"]
        options: list[dict[str, Any]] = []
        for record in context["records"]:
            options.append(
                {
                    "value": record["id"],
                    "label": record["label"],
                    "display_json": dumps_json(record["values"]),
                }
            )
        field["master_options"] = options


def validate_master_references(storage: Any, fields: list[dict[str, Any]], data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    id_cache: dict[str, set[str]] = {}

    def valid_ids(form_id: str) -> set[str]:
        if form_id not in id_cache:
            id_cache[form_id] = {
                str(item.get("id", ""))
                for item in storage.submissions.list_submissions(form_id)
                if item.get("id")
            }
        return id_cache[form_id]

    def validate(field_list: list[dict[str, Any]], target: dict[str, Any]) -> None:
        if not isinstance(target, dict):
            return
        for field in field_list:
            key = str(field.get("key", "")).strip()
            if not key:
                continue
            value = target.get(key)
            if field.get("type") == "group":
                children = field.get("children") or []
                if field.get("is_array"):
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                validate(children, item)
                elif isinstance(value, dict):
                    validate(children, value)
                continue

            if field.get("type") != "master":
                continue

            source_form_id = str(field.get("master_form_id", "")).strip()
            if not source_form_id:
                continue
            master_ids = valid_ids(source_form_id)
            label = field.get("label") or key

            if field.get("is_array"):
                if not isinstance(value, list):
                    continue
                invalid = [item for item in value if item not in (None, "") and str(item) not in master_ids]
                if invalid:
                    errors.append(f"{label}: 選択値に無効な項目があります")
            else:
                if value in (None, ""):
                    continue
                if str(value) not in master_ids:
                    errors.append(f"{label}: 選択値が不正です")

    validate(fields, data)
    return errors

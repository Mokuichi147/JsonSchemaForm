from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemaform.utils import dumps_json


def flatten_fields(
    fields: list[dict[str, Any]],
    prefix: str = "",
    label_prefix: str = "",
    expand_rows_for_group_arrays: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in fields:
        key = f"{prefix}{field['key']}" if prefix else field["key"]
        label = f"{label_prefix}{field.get('label') or field['key']}" if label_prefix else (field.get("label") or field["key"])
        if field.get("type") == "group":
            if field.get("is_array"):
                if expand_rows_for_group_arrays and field.get("expand_rows"):
                    children = field.get("children") or []
                    result.extend(
                        flatten_fields(
                            children,
                            prefix=key + ".",
                            label_prefix=label + ".",
                            expand_rows_for_group_arrays=expand_rows_for_group_arrays,
                        )
                    )
                else:
                    result.append({**field, "flat_key": key, "flat_label": label})
            else:
                children = field.get("children") or []
                result.extend(
                    flatten_fields(
                        children,
                        prefix=key + ".",
                        label_prefix=label + ".",
                        expand_rows_for_group_arrays=expand_rows_for_group_arrays,
                    )
                )
        else:
            result.append({**field, "flat_key": key, "flat_label": label})
    return result


def flatten_filter_fields(
    fields: list[dict[str, Any]],
    prefix: str = "",
    label_prefix: str = "",
    in_array_context: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in fields:
        key = f"{prefix}{field['key']}" if prefix else field["key"]
        label = (
            f"{label_prefix}{field.get('label') or field['key']}"
            if label_prefix
            else (field.get("label") or field["key"])
        )
        field_type = field.get("type")
        is_array = bool(field.get("is_array"))
        effective_is_array = is_array or in_array_context

        if field_type == "group":
            children = field.get("children") or []
            if is_array:
                # 配列グループ本体のフィルタを残しつつ、子要素もフィルタ可能にする。
                result.append({**field, "flat_key": key, "flat_label": label, "is_array": True})
                result.extend(
                    flatten_filter_fields(
                        children,
                        prefix=key + ".",
                        label_prefix=label + ".",
                        in_array_context=True,
                    )
                )
            else:
                result.extend(
                    flatten_filter_fields(
                        children,
                        prefix=key + ".",
                        label_prefix=label + ".",
                        in_array_context=in_array_context,
                    )
                )
            continue

        result.append({**field, "flat_key": key, "flat_label": label, "is_array": effective_is_array})
    return result


def _build_child_map(children: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for child in children:
        mapping[child["key"]] = child
    return mapping


def _label_for_field(field: dict[str, Any], fallback_key: str) -> str:
    return field.get("label") or field.get("key") or fallback_key


def _format_value_by_field(value: Any, field: dict[str, Any]) -> Any:
    if field.get("type") != "group":
        return value
    children = field.get("children") or []
    if field.get("is_array"):
        if not isinstance(value, list):
            return value
        return [
            _format_group_item(item, children)
            if isinstance(item, dict)
            else item
            for item in value
        ]
    if isinstance(value, dict):
        return _format_group_item(value, children)
    return value


def _format_group_item(item: dict[str, Any], children: list[dict[str, Any]]) -> dict[str, Any]:
    child_map = _build_child_map(children)
    formatted: dict[str, Any] = {}
    for key, raw_value in item.items():
        child = child_map.get(key)
        if child:
            label = _label_for_field(child, key)
            formatted[label] = _format_value_by_field(raw_value, child)
        else:
            formatted[key] = raw_value
    return formatted


def format_array_group_value(value: Any, children: list[dict[str, Any]]) -> str:
    if not value or not isinstance(value, list):
        return ""
    result: list[Any] = []
    for item in value:
        if isinstance(item, dict):
            result.append(_format_group_item(item, children))
        else:
            result.append(item)
    return dumps_json(result)


def get_nested_value(data: dict[str, Any], dotted_key: str) -> Any:
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def set_nested_value(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def clean_empty_recursive(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            result = clean_empty_recursive(v)
            if result is not None and result != "":
                cleaned[k] = result
        return cleaned if cleaned else None
    if isinstance(data, list):
        cleaned_list = []
        for item in data:
            result = clean_empty_recursive(item)
            if result is not None and result != "":
                cleaned_list.append(result)
        return cleaned_list if cleaned_list else None
    return data


def _expand_value_by_field(field: dict[str, Any], value: Any) -> list[Any]:
    if field.get("type") != "group":
        return [deepcopy(value)]

    children = field.get("children") or []
    if field.get("is_array"):
        if not field.get("expand_rows"):
            if value is None:
                return [[]]
            return [deepcopy(value)]
        if not isinstance(value, list) or not value:
            return [{}]
        expanded_items: list[Any] = []
        for item in value:
            if isinstance(item, dict):
                item_variants = _expand_object_by_children(children, item)
            else:
                item_variants = [deepcopy(item)]
            for item_variant in item_variants:
                expanded_items.append(item_variant)
        return expanded_items

    if isinstance(value, dict):
        return _expand_object_by_children(children, value)
    return _expand_object_by_children(children, {})


def _expand_object_by_children(children: list[dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    child_keys = {child["key"] for child in children}
    base_extras = {k: deepcopy(v) for k, v in source.items() if k not in child_keys}
    variants: list[dict[str, Any]] = [base_extras]

    for child in children:
        key = child["key"]
        expanded_values = _expand_value_by_field(child, source.get(key))
        next_variants: list[dict[str, Any]] = []
        for base in variants:
            for expanded_value in expanded_values:
                row = dict(base)
                row[key] = expanded_value
                next_variants.append(row)
        variants = next_variants

    return variants or [base_extras]


def expand_group_array_rows(fields: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return [{}]

    top_keys = {field["key"] for field in fields}
    base_extras = {k: deepcopy(v) for k, v in data.items() if k not in top_keys}
    variants: list[dict[str, Any]] = [base_extras]

    for field in fields:
        key = field["key"]
        expanded_values = _expand_value_by_field(field, data.get(key))
        next_variants: list[dict[str, Any]] = []
        for base in variants:
            for expanded_value in expanded_values:
                row = dict(base)
                row[key] = expanded_value
                next_variants.append(row)
        variants = next_variants

    return variants or [base_extras]

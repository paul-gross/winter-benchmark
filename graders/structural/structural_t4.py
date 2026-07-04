#!/usr/bin/env python3
"""Structural checks for the repository-split task (t4/t5).

Run inside the submission's own environment (`uv run python structural_t4.py`)
from a cwd where `wts_persistence` is importable — the mono repo root, or the
wts-persistence repo in poly. Encodes ONLY constraints the prompt states:

- protocols-frozen: the public Protocols keep their method surface (exact
  signatures in t4; with --renamed-field, the t3 rename is allowed to touch the
  item-field argument/annotation names).
- no-inheritance: the write adapter wired into the app (WriteItemRepository —
  its import site, api deps.py, is outside the persistence layer and therefore
  unchanged by the prompt's own constraint) no longer inherits its read
  operations from a concrete read implementation.
- distinct-read-impl: a distinct concrete read implementation exists.

Prints one JSON object to stdout; never raises for a graded failure.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil


def is_protocol(cls: type) -> bool:
    return bool(getattr(cls, "_is_protocol", False))


def normalized_signature(func, renamed_field: str | None) -> str:
    sig = str(inspect.signature(func))
    if renamed_field:
        sig = sig.replace(renamed_field, "label")
    return sig.replace("'", "").replace('"', "")


EXPECTED = {
    "IReadItemRepository": {
        "ping": "(self) -> bool",
        "list_items": "(self, limit: int = 100) -> list[Item]",
    },
    "IWriteItemRepository": {
        "init_schema": "(self) -> None",
        "add_item": "(self, label: str, source: ItemSource) -> Item",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--renamed-field",
        default=None,
        help="Accept this field name where the original said 'label' (t5: title)",
    )
    args = parser.parse_args()

    result: dict = {"protocols_frozen": False, "no_inheritance": False, "distinct_read_impl": False, "details": []}

    try:
        protocols_mod = importlib.import_module("wts_persistence.repositories.item_repository")
        internal_mod = importlib.import_module("wts_persistence.internal.item_repository")
    except Exception as exc:  # noqa: BLE001 — a graded failure, not a grader crash
        result["details"].append(f"import failed: {exc}")
        print(json.dumps(result))
        return

    # --- protocols-frozen -------------------------------------------------
    frozen = True
    for proto_name, methods in EXPECTED.items():
        proto = getattr(protocols_mod, proto_name, None)
        if proto is None or not is_protocol(proto):
            frozen = False
            result["details"].append(f"protocol {proto_name} missing or no longer a Protocol")
            continue
        for method, expected_sig in methods.items():
            func = getattr(proto, method, None)
            if func is None:
                frozen = False
                result["details"].append(f"{proto_name}.{method} missing")
                continue
            if args.renamed_field:
                continue  # rename in play: method presence only
            actual = normalized_signature(func, None)
            if actual != expected_sig:
                frozen = False
                result["details"].append(
                    f"{proto_name}.{method} signature changed: {actual!r} != {expected_sig!r}"
                )
    # No new abstract members either: the Protocols are "unchanged".
    for proto_name in EXPECTED:
        proto = getattr(protocols_mod, proto_name, None)
        if proto is None:
            continue
        members = {
            n
            for n, v in vars(proto).items()
            if callable(v) and not n.startswith("_")
        }
        extra = members - set(EXPECTED[proto_name])
        if proto_name == "IWriteItemRepository":
            extra -= set(EXPECTED["IReadItemRepository"])
        if extra:
            frozen = False
            result["details"].append(f"{proto_name} gained members: {sorted(extra)}")
    result["protocols_frozen"] = frozen

    # --- no-inheritance ---------------------------------------------------
    write_cls = getattr(internal_mod, "WriteItemRepository", None)
    if write_cls is None:
        result["details"].append(
            "WriteItemRepository not found in wts_persistence.internal.item_repository "
            "(its import site outside the persistence layer may not change)"
        )
    else:
        offending = [
            base.__name__
            for base in write_cls.__mro__[1:]
            if base is not object and not is_protocol(base) and "list_items" in vars(base)
        ]
        result["no_inheritance"] = not offending
        if offending:
            result["details"].append(
                f"write implementation inherits read operations from: {offending}"
            )

    # --- distinct-read-impl ------------------------------------------------
    package = importlib.import_module("wts_persistence")
    read_impls = []
    for info in pkgutil.walk_packages(package.__path__, prefix="wts_persistence."):
        try:
            mod = importlib.import_module(info.name)
        except Exception:  # noqa: BLE001
            continue
        for name, obj in vars(mod).items():
            if (
                inspect.isclass(obj)
                and obj.__module__ == info.name
                and not is_protocol(obj)
                and "list_items" in vars(obj)
                and "add_item" not in vars(obj)
                and obj is not write_cls
            ):
                read_impls.append(f"{info.name}.{name}")
    result["distinct_read_impl"] = bool(read_impls)
    result["read_impls"] = sorted(set(read_impls))

    print(json.dumps(result))


if __name__ == "__main__":
    main()

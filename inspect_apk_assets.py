#!/usr/bin/env python3
"""Build a small, inspectable index of the unpacked Zombie Castaways APK.

Run from the APK repository root:
    py inspect_apk_assets.py

Inputs (when present): inventory.csv, desc.txt, comp_manifest_pretty.json
Outputs: apk_desc_asset_map.csv, apk_inventory_summary.json,
         comp_manifest_summary.json, comp_manifest_parts/*.json

The script does not modify or decode any original APK files. Manifest fragments
are valid JSON envelopes with a JSON path so individual parts stay readable.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def detect_encoding(path: Path) -> str:
    raw = path.read_bytes()[:4]
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    return "utf-8-sig"


def read_inventory(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    if not path.exists():
        return result
    with path.open("r", encoding=detect_encoding(path), newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Path") or row.get("path") or "").strip().replace("/", "\\")
            raw_size = row.get("Length") or row.get("length") or ""
            try:
                result[name] = int(raw_size)
            except (TypeError, ValueError):
                continue
    return result


def lookup_size(inventory: dict[str, int], resource_path: str) -> tuple[str, int | None]:
    name = resource_path.strip().lstrip("/\\").replace("/", "\\")
    candidates = [name, "assets\\" + name]
    for candidate in candidates:
        if candidate in inventory:
            return candidate, inventory[candidate]
    return "", None


def parse_desc(desc_path: Path, inventory: dict[str, int], out_csv: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    rows: list[dict[str, str | int]] = []
    if not desc_path.exists():
        return {}
    with desc_path.open("r", encoding=detect_encoding(desc_path)) as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or "=" not in line:
                continue
            left, right = line.split("=", 1)
            left, right = left.strip(), right.strip()
            if not right:
                continue
            if left.startswith("particle:"):
                category = "particle_definition"
                logical_name = left[len("particle:"):]
                symbol = ""
            elif "/" in left:
                category = "composition_texture_reference"
                logical_name, symbol = left.split("/", 1)
            else:
                category = "named_resource_alias"
                logical_name, symbol = left, ""
            file_path = right.lstrip("/\\")
            matched_path, size = lookup_size(inventory, file_path)
            ext = Path(file_path).suffix.lower()
            counts[category] += 1
            rows.append({
                "desc_line": line_no,
                "category": category,
                "logical_name": logical_name,
                "symbol": symbol,
                "resource_path": file_path,
                "extension": ext,
                "inventory_path": matched_path,
                "size_bytes": "" if size is None else size,
                "inventory_match": "yes" if size is not None else "no",
            })
    if rows:
        with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return dict(counts)


def json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def make_envelope(path_tokens: list[Any], payload_key: str, payload: Any, extra: dict[str, Any] | None = None) -> bytes:
    envelope: dict[str, Any] = {"json_path": path_tokens, payload_key: payload}
    if extra:
        envelope.update(extra)
    return json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")


def json_kind(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def manifest_summary(manifest_path: Path, out_path: Path, parts_dir: Path, max_bytes: int) -> None:
    if not manifest_path.exists():
        return
    with manifest_path.open("r", encoding=detect_encoding(manifest_path)) as f:
        data = json.load(f)

    summary: dict[str, Any] = {
        "source_file": manifest_path.name,
        "source_size_bytes": manifest_path.stat().st_size,
        "root_type": json_kind(data),
        "root_count": len(data) if isinstance(data, (dict, list)) else None,
        "top_level": [],
    }
    if isinstance(data, dict):
        for key, value in data.items():
            entry: dict[str, Any] = {"key": str(key), "type": json_kind(value)}
            if isinstance(value, (dict, list)):
                entry["count"] = len(value)
                entry["compact_size_bytes"] = json_size(value)
                if isinstance(value, dict):
                    entry["sample_keys"] = [str(k) for k in list(value.keys())[:12]]
            elif isinstance(value, str):
                entry["string_length"] = len(value)
            summary["top_level"].append(entry)
    elif isinstance(data, list):
        summary["sample_items"] = [
            {"index": i, "type": json_kind(item), "compact_size_bytes": json_size(item)}
            for i, item in enumerate(data[:25])
        ]

    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if parts_dir.exists():
        for item in parts_dir.iterdir():
            if item.is_file():
                item.unlink()
    parts_dir.mkdir(parents=True, exist_ok=True)
    part_no = 0

    def save_encoded(encoded: bytes, path_tokens: list[Any]) -> None:
        nonlocal part_no
        if len(encoded) > max_bytes:
            raise ValueError(f"One JSON fragment is larger than {max_bytes} bytes at path {path_tokens}")
        part_no += 1
        (parts_dir / f"part_{part_no:03d}.json").write_bytes(encoded)

    def split_node(node: Any, path_tokens: list[Any]) -> None:
        whole = make_envelope(path_tokens, "value", node)
        if len(whole) <= max_bytes:
            save_encoded(whole, path_tokens)
            return

        if isinstance(node, dict):
            batch: dict[str, Any] = {}
            for key, value in node.items():
                k = str(key)
                candidate = dict(batch)
                candidate[k] = value
                if batch and len(make_envelope(path_tokens, "entries", candidate)) > max_bytes:
                    save_encoded(make_envelope(path_tokens, "entries", batch), path_tokens)
                    batch = {}

                single_env = make_envelope(path_tokens, "entries", {k: value})
                if len(single_env) > max_bytes:
                    if batch:
                        save_encoded(make_envelope(path_tokens, "entries", batch), path_tokens)
                        batch = {}
                    split_node(value, path_tokens + [k])
                else:
                    batch[k] = value
            if batch:
                save_encoded(make_envelope(path_tokens, "entries", batch), path_tokens)

        elif isinstance(node, list):
            batch: list[Any] = []
            start_index = 0
            for index, value in enumerate(node):
                candidate = batch + [value]
                if batch and len(make_envelope(path_tokens, "items", candidate, {"start_index": start_index})) > max_bytes:
                    save_encoded(make_envelope(path_tokens, "items", batch, {"start_index": start_index}), path_tokens)
                    start_index = index
                    batch = []

                single_env = make_envelope(path_tokens, "items", [value], {"start_index": index})
                if len(single_env) > max_bytes:
                    if batch:
                        save_encoded(make_envelope(path_tokens, "items", batch, {"start_index": start_index}), path_tokens)
                        batch = []
                    split_node(value, path_tokens + [index])
                    start_index = index + 1
                else:
                    batch.append(value)
            if batch:
                save_encoded(make_envelope(path_tokens, "items", batch, {"start_index": start_index}), path_tokens)
        else:
            raise ValueError(f"Cannot split oversized scalar at JSON path {path_tokens}")

    split_node(data, [])
    summary["fragment_count"] = part_no
    summary["fragment_max_bytes"] = max_bytes
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default="inventory.csv")
    parser.add_argument("--desc", default="desc.txt")
    parser.add_argument("--manifest", default="comp_manifest_pretty.json")
    parser.add_argument("--max-fragment-bytes", type=int, default=700_000)
    args = parser.parse_args()

    root = Path.cwd()
    inventory = read_inventory(root / args.inventory)
    inv_summary = {
        "source_file": args.inventory,
        "file_count": len(inventory),
        "total_bytes": sum(inventory.values()),
        "extensions": dict(Counter(Path(name).suffix.lower() or "[none]" for name in inventory)),
        "largest_files": sorted(
            ({"path": k, "size_bytes": v} for k, v in inventory.items()),
            key=lambda x: x["size_bytes"], reverse=True
        )[:30],
    }
    (root / "apk_inventory_summary.json").write_text(
        json.dumps(inv_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    desc_counts = parse_desc(root / args.desc, inventory, root / "apk_desc_asset_map.csv")
    inv_summary["desc_entry_counts"] = desc_counts
    (root / "apk_inventory_summary.json").write_text(
        json.dumps(inv_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest_summary(
        root / args.manifest,
        root / "comp_manifest_summary.json",
        root / "comp_manifest_parts",
        args.max_fragment_bytes,
    )
    print("Finished. Files created:")
    for name in ["apk_desc_asset_map.csv", "apk_inventory_summary.json", "comp_manifest_summary.json"]:
        if (root / name).exists():
            print(f"  {name}")
    parts = root / "comp_manifest_parts"
    if parts.exists():
        print(f"  {parts}/ ({sum(1 for p in parts.glob('*.json'))} fragments)")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}")
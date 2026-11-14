#!/usr/bin/env python3
"""Cross-reference original VK Zombie Farm item animations with APK assets.

Run from the unpacked APK repository root, for example:
    py analyze_zombifarm_overlap_v2.py --items "C:\\games\\ZombieFarm\\items.json"

Or copy the original social-game items.json into this folder and run:
    py analyze_zombifarm_overlap_v2.py --items .\\items.json

Required inputs:
    inventory.csv
    assets/desc.txt
    --items <original social Zombie Farm items.json>
Optional:
    desc.txt

Outputs:
    legacy_item_comp_matches.csv       one row per old item -> comp mapping
    legacy_item_asset_families.csv     child anim_obj/spr/mobj/anim resources
    assets_desc_compositions.csv      compact list of comp resources
    legacy_overlap_summary.json        counts and input validation

The script deliberately stops if the social-game items.json cannot be found or
contains no usable records. It never silently produces an empty "successful" match.
Name matches are candidates only: verify artwork visually before reuse.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig", errors="replace")


def read_inventory(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise SystemExit(f"Не найден inventory.csv: {path}\nПоложи inventory.csv в корень APK-репозитория или укажи --inventory.")
    out: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("Path") or row.get("path") or "").strip().replace("/", "\\")
            size = row.get("Length") or row.get("length") or ""
            try:
                out[name.casefold()] = int(size)
            except (TypeError, ValueError):
                continue
    if not out:
        raise SystemExit(f"В {path} не удалось прочитать ни одной строки. Проверь заголовки Path и Length.")
    return out


def lookup_inventory(inventory: dict[str, int], resource: str) -> tuple[str, int | None]:
    name = resource.strip().lstrip("/\\").replace("/", "\\")
    for candidate in (name, "assets\\" + name):
        size = inventory.get(candidate.casefold())
        if size is not None:
            return candidate, size
    return "", None


def classify_key(key: str) -> tuple[str, str]:
    for prefix in ("anim_obj:", "anim:", "spr:", "mobj:", "comp:", "particle:"):
        if key.startswith(prefix):
            return prefix[:-1], key[len(prefix):]
    return "named_resource", key


def parse_descriptor(path: Path, inventory: dict[str, int]) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SystemExit(f"Не найден файл описания ресурсов: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(read_text(path).splitlines(), 1):
        if "=" not in line:
            continue
        key, resource = (part.strip() for part in line.split("=", 1))
        if not key or not resource:
            continue
        kind, logical_name = classify_key(key)
        inventory_path, size = lookup_inventory(inventory, resource)
        rows.append({
            "descriptor_line": line_no,
            "logical_key": key,
            "kind": kind,
            "logical_name": logical_name,
            "resource_file": resource.lstrip("/\\"),
            "inventory_path": inventory_path,
            "size_bytes": "" if size is None else size,
            "inventory_match": "yes" if size is not None else "no",
        })
    return rows


def load_items(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        raise SystemExit(
            "Не найден исходный items.json социальной Зомби Фермы:\n"
            f"  {path}\n"
            "Скопируй исходный items.json в корень APK-репозитория и запусти "
            "--items .\\items.json, либо укажи полный путь к файлу. "
            "Без этого файла сопоставление предметов не выполняется."
        )
    data = json.loads(read_text(path))
    if isinstance(data, dict):
        data = data.get("items", data.get("entities", []))
    if not isinstance(data, list):
        raise SystemExit(f"Ожидался JSON-массив в {path}, получен {type(data).__name__}.")
    raw_count = len(data)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(item)
    if not unique:
        raise SystemExit(f"Файл {path} прочитан, но в нём нет записей-объектов. Проверь, что это items.json социальной игры.")
    return unique, raw_count


def animation_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v)]
    if isinstance(value, str):
        return [value] if value else []
    return [str(value)]


def candidates(anim: str) -> list[tuple[str, str]]:
    out = [(anim, "exact_objAnim_name")]
    shortened = re.sub(r"_0?\d{1,2}$", "", anim)
    if shortened != anim:
        out.append((shortened, "removed_numeric_objAnim_suffix"))
    if anim.endswith("_base"):
        out.append((anim[:-5], "removed_base_suffix"))
    result = []
    seen = set()
    for name, method in out:
        if name.casefold() not in seen:
            seen.add(name.casefold())
            result.append((name, method))
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", default="inventory.csv")
    ap.add_argument("--assets-desc", default="assets/desc.txt")
    ap.add_argument("--small-desc", default="desc.txt")
    ap.add_argument("--items", required=True, help="Path to original social Zombie Farm items.json")
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    root = Path.cwd()
    inventory_path = Path(args.inventory).expanduser()
    if not inventory_path.is_absolute(): inventory_path = root / inventory_path
    items_path = Path(args.items).expanduser()
    if not items_path.is_absolute(): items_path = root / items_path
    assets_desc_path = Path(args.assets_desc).expanduser()
    if not assets_desc_path.is_absolute(): assets_desc_path = root / assets_desc_path
    small_desc_path = Path(args.small_desc).expanduser()
    if not small_desc_path.is_absolute(): small_desc_path = root / small_desc_path
    out_dir = Path(args.output_dir).expanduser()
    if not out_dir.is_absolute(): out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = read_inventory(inventory_path)
    items, raw_item_count = load_items(items_path)
    desc_rows = parse_descriptor(assets_desc_path, inventory)
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in desc_rows:
        by_key[row["logical_key"]].append(row)

    comp_rows = [r for r in desc_rows if r["kind"] == "comp"]
    write_csv(out_dir / "assets_desc_compositions.csv", comp_rows)

    match_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    matched_items: set[str] = set()
    matched_anim_values: set[str] = set()
    methods = Counter()
    for item in items:
        item_id = str(item.get("id", ""))
        item_type = str(item.get("type", ""))
        title = str(item.get("title") or item.get("name") or "")
        for anim in animation_values(item.get("objAnim")):
            for base, method in candidates(anim):
                comp_key = f"comp:{base}"
                for comp in by_key.get(comp_key, []):
                    match_rows.append({
                        "item_id": item_id,
                        "item_type": item_type,
                        "item_title": title,
                        "objAnim": anim,
                        "candidate_base": base,
                        "matched_logical_key": comp_key,
                        "composition_file": comp["resource_file"],
                        "inventory_path": comp["inventory_path"],
                        "composition_size_bytes": comp["size_bytes"],
                        "match_method": method,
                        "evidence_level": "logical name match only; visual identity unverified",
                    })
                    matched_items.add(item_id)
                    matched_anim_values.add(anim)
                    methods[method] += 1
                    prefixes = {
                        "anim_obj": f"anim_obj:{base}_",
                        "spr": f"spr:{base}_",
                        "mobj": f"mobj:{base}_",
                        "anim": f"anim:{base}_",
                    }
                    for kind, prefix in prefixes.items():
                        for key, rows in by_key.items():
                            if key.startswith(prefix):
                                for resource in rows:
                                    family_rows.append({
                                        "item_id": item_id,
                                        "item_type": item_type,
                                        "item_title": title,
                                        "objAnim": anim,
                                        "composition_key": comp_key,
                                        "component_kind": kind,
                                        "component_key": key,
                                        "resource_file": resource["resource_file"],
                                        "inventory_path": resource["inventory_path"],
                                        "size_bytes": resource["size_bytes"],
                                        "inventory_match": resource["inventory_match"],
                                    })

    def dedup(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
        d = {}
        for r in rows:
            d[tuple(str(r.get(k, "")) for k in key_fields)] = r
        return list(d.values())

    match_rows = dedup(match_rows, ("item_id", "objAnim", "matched_logical_key", "composition_file"))
    family_rows = dedup(family_rows, ("item_id", "objAnim", "component_key", "resource_file"))
    write_csv(out_dir / "legacy_item_comp_matches.csv", match_rows)
    write_csv(out_dir / "legacy_item_asset_families.csv", family_rows)

    small_rows = parse_descriptor(small_desc_path, inventory) if small_desc_path.is_file() else []
    summary = {
        "items_file": str(items_path.resolve()),
        "items_raw_rows": raw_item_count,
        "items_after_exact_dedup": len(items),
        "unique_objAnim_values": len({v for it in items for v in animation_values(it.get("objAnim"))}),
        "inventory_file": str(inventory_path.resolve()),
        "inventory_rows": len(inventory),
        "assets_desc_file": str(assets_desc_path.resolve()),
        "assets_desc_rows": len(desc_rows),
        "composition_keys_in_assets_desc": len(comp_rows),
        "assets_desc_rows_without_inventory_match": sum(1 for r in desc_rows if r["inventory_match"] != "yes"),
        "small_desc_rows": len(small_rows),
        "matched_item_ids": len(matched_items),
        "matched_objAnim_values": len(matched_anim_values),
        "item_to_composition_rows": len(match_rows),
        "item_to_component_rows": len(family_rows),
        "match_methods": dict(methods),
        "warning": "Name-based matches are candidates only. They do not prove Castaways artwork is identical to social Zombie Farm artwork; compare visual appearance, dimensions, animation and composition.",
    }
    (out_dir / "legacy_overlap_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}")

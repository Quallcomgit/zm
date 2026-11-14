#!/usr/bin/env python3
"""Cross-reference the original VK Zombie Farm items.json with the APK asset catalog.

Run from the unpacked APK repository root:
    py analyze_zombifarm_overlap.py --items ..\\items.json

Inputs:
    inventory.csv
    assets/desc.txt        (the large, primary resource-name mapping)
    desc.txt              (optional small effect/particle descriptor)
    comp_manifest_pretty.json (optional, separate composition manifest)
    items.json            (original social Zombie Farm catalog; pass with --items)

Outputs:
    assets_desc_index.csv
    legacy_item_asset_candidates.csv
    legacy_overlap_summary.json

Important: matches based on shortened object-animation names are candidates, not proof
that the Castaways image is pixel-identical to the historical VK asset. Every mapping
retains its evidence type for manual/visual validation.
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
    out: dict[str, int] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("Path") or row.get("path") or "").strip().replace("/", "\\")
            raw_size = row.get("Length") or row.get("length") or ""
            try:
                out[name.casefold()] = int(raw_size)
            except (TypeError, ValueError):
                continue
    return out


def lookup_inventory(inventory: dict[str, int], resource: str) -> tuple[str, int | None]:
    name = resource.strip().lstrip("/\\").replace("/", "\\")
    candidates = [name, "assets\\" + name]
    for candidate in candidates:
        size = inventory.get(candidate.casefold())
        if size is not None:
            return candidate, size
    return "", None


def classify_key(key: str) -> tuple[str, str]:
    prefixes = ("anim_obj:", "anim:", "spr:", "mobj:", "comp:", "particle:")
    for prefix in prefixes:
        if key.startswith(prefix):
            return prefix[:-1], key[len(prefix):]
    return "named_resource", key


def parse_descriptor(path: Path, inventory: dict[str, int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, raw in enumerate(read_text(path).splitlines(), 1):
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, resource = line.split("=", 1)
        key, resource = key.strip(), resource.strip()
        if not key or not resource:
            continue
        kind, logical_name = classify_key(key)
        path_in_inventory, size = lookup_inventory(inventory, resource)
        rows.append({
            "descriptor": str(path).replace("\\", "/"),
            "line": line_no,
            "logical_key": key,
            "kind": kind,
            "logical_name": logical_name,
            "resource_file": resource.lstrip("/\\"),
            "inventory_path": path_in_inventory,
            "size_bytes": "" if size is None else size,
            "inventory_match": "yes" if size is not None else "no",
        })
    return rows


def load_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(read_text(path))
    if isinstance(data, dict):
        data = data.get("items", data.get("entities", []))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    # Deduplicate exact duplicate records, but preserve different definitions sharing an ID.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
    return unique


def animation_values(item: dict[str, Any]) -> list[str]:
    value = item.get("objAnim")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v)]
    return [str(value)]


def name_candidates(obj_anim: str) -> list[tuple[str, str]]:
    """Return conservative name candidates with an explicit evidence label."""
    result = [(obj_anim, "exact_objAnim_name")]
    # Old catalog often uses a numbered state suffix (e.g. b_babel_01), while
    # the APK catalog groups the same family under comp:b_babel and frames b_babel_0..N.
    shortened = re.sub(r"_0?\d{1,2}$", "", obj_anim)
    if shortened != obj_anim:
        result.append((shortened, "removed_numeric_objAnim_suffix"))
    if obj_anim.endswith("_base"):
        result.append((obj_anim[:-5], "removed_base_suffix"))
    # Keep order, remove duplicate candidate names.
    out: list[tuple[str, str]] = []
    used: set[str] = set()
    for name, method in result:
        if name and name.casefold() not in used:
            used.add(name.casefold())
            out.append((name, method))
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fields or list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", default="inventory.csv")
    ap.add_argument("--assets-desc", default="assets/desc.txt")
    ap.add_argument("--small-desc", default="desc.txt")
    ap.add_argument("--items", default="items.json", help="Original VK Zombie Farm items.json")
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    root = Path.cwd()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory = read_inventory(root / args.inventory)
    if not inventory:
        raise SystemExit(f"No inventory rows read from {root / args.inventory}")

    big_desc_path = root / args.assets_desc
    small_desc_path = root / args.small_desc
    big_rows = parse_descriptor(big_desc_path, inventory)
    small_rows = parse_descriptor(small_desc_path, inventory)
    all_desc_rows = big_rows + small_rows
    write_csv(out_dir / "assets_desc_index.csv", all_desc_rows)

    # Index all logical keys. Some keys can appear more than once; keep all candidates.
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in big_rows:
        by_key[row["logical_key"]].append(row)

    items_path = root / args.items
    items = load_items(items_path)
    candidate_rows: list[dict[str, Any]] = []
    covered_items: set[str] = set()
    matched_obj_anim_values: set[str] = set()
    methods = Counter()

    for item in items:
        item_id = str(item.get("id", ""))
        item_type = str(item.get("type", ""))
        item_name = str(item.get("name") or item.get("title") or "")
        for obj_anim in animation_values(item):
            for candidate, method in name_candidates(obj_anim):
                # Composition-level mapping is the most useful bridge from the old catalog.
                keys_to_try = [f"comp:{candidate}"]
                # Also include direct component keys if they exist exactly.
                keys_to_try += [
                    f"anim_obj:{candidate}",
                    f"spr:{candidate}",
                    f"mobj:{candidate}",
                    f"anim:{candidate}/{candidate}",
                ]
                for key in keys_to_try:
                    for desc_row in by_key.get(key, []):
                        row = {
                            "item_id": item_id,
                            "item_type": item_type,
                            "item_name": item_name,
                            "objAnim_original": obj_anim,
                            "candidate_name": candidate,
                            "match_method": method,
                            "matched_logical_key": key,
                            "resource_kind": desc_row["kind"],
                            "resource_file": desc_row["resource_file"],
                            "inventory_path": desc_row["inventory_path"],
                            "size_bytes": desc_row["size_bytes"],
                            "inventory_match": desc_row["inventory_match"],
                            "evidence_note": "Name-family match only; visually verify before treating as original VK art",
                        }
                        candidate_rows.append(row)
                        covered_items.add(item_id)
                        matched_obj_anim_values.add(obj_anim)
                        methods[method] += 1

                # For a matched composition base, include its frame-level family records.
                # This maps all pieces (anim PNG, anim_obj BIN, spr BIN, mobj BIN) that
                # share the base prefix, rather than only the composition .bin.
                comp_key = f"comp:{candidate}"
                if comp_key in by_key:
                    prefix_map = {
                        "anim_obj": f"anim_obj:{candidate}_",
                        "spr": f"spr:{candidate}_",
                        "mobj": f"mobj:{candidate}_",
                        "anim": f"anim:{candidate}_",
                    }
                    for kind, prefix in prefix_map.items():
                        for logical_key, desc_matches in by_key.items():
                            if logical_key.startswith(prefix):
                                for desc_row in desc_matches:
                                    row = {
                                        "item_id": item_id,
                                        "item_type": item_type,
                                        "item_name": item_name,
                                        "objAnim_original": obj_anim,
                                        "candidate_name": candidate,
                                        "match_method": method + "+base_family",
                                        "matched_logical_key": logical_key,
                                        "resource_kind": desc_row["kind"],
                                        "resource_file": desc_row["resource_file"],
                                        "inventory_path": desc_row["inventory_path"],
                                        "size_bytes": desc_row["size_bytes"],
                                        "inventory_match": desc_row["inventory_match"],
                                        "evidence_note": "Composition base plus same-name family; visually verify before treating as original VK art",
                                    }
                                    candidate_rows.append(row)
                                    covered_items.add(item_id)
                                    matched_obj_anim_values.add(obj_anim)

    # De-duplicate rows created by multiple objAnim values/candidate routes.
    dedup: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in candidate_rows:
        key = tuple(str(row[k]) for k in (
            "item_id", "objAnim_original", "matched_logical_key", "resource_file", "match_method"
        ))
        dedup[key] = row
    candidate_rows = list(dedup.values())
    write_csv(out_dir / "legacy_item_asset_candidates.csv", candidate_rows)

    kind_counts = Counter(row["kind"] for row in big_rows)
    matched_counts = Counter(row["inventory_match"] for row in big_rows)
    comp_keys = [row for row in big_rows if row["kind"] == "comp"]
    anim_keys = [row for row in big_rows if row["kind"] == "anim"]

    summary = {
        "inventory_file_count": len(inventory),
        "inventory_total_bytes": sum(inventory.values()),
        "assets_desc_path": str(big_desc_path).replace("\\", "/"),
        "assets_desc_entries": len(big_rows),
        "assets_desc_resource_kind_counts": dict(kind_counts),
        "assets_desc_inventory_match_counts": dict(matched_counts),
        "assets_desc_composition_keys": len(comp_keys),
        "assets_desc_animation_png_keys": len(anim_keys),
        "small_desc_entries": len(small_rows),
        "original_items_file": str(items_path).replace("\\", "/"),
        "original_items_after_exact_dedup": len(items),
        "unique_objAnim_values": len({v for item in items for v in animation_values(item)}),
        "items_with_candidate_asset_links": len(covered_items),
        "unique_objAnim_values_with_candidate_asset_links": len(matched_obj_anim_values),
        "candidate_link_rows_after_dedup": len(candidate_rows),
        "candidate_match_method_counts": dict(methods),
        "warning": "Castaways asset-name matches are candidates. They do not prove the asset is byte-identical to the original VK/Flash art. Check visuals, dimensions, animation and composition before reuse.",
    }
    (out_dir / "legacy_overlap_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Finished.")
    print(f"  assets/desc entries: {len(big_rows)}")
    print(f"  composition keys: {len(comp_keys)}")
    print(f"  original items: {len(items)}")
    print(f"  items with candidate asset links: {len(covered_items)}")
    print(f"  output: {out_dir.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}")

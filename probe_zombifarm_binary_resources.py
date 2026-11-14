#!/usr/bin/env python3
"""Probe binary resources referenced by the Zombie Farm ↔ Castaways asset matches.

Run from the unpacked APK repository root (the directory containing assets/):
    py probe_zombifarm_binary_resources.py

Inputs:
    legacy_item_comp_matches.csv
    legacy_item_asset_families.csv
    assets/ (or pass --assets-dir)

Outputs in binary_probe/:
    binary_resource_probe.csv
    binary_probe_summary.json
    protobuf_wire_candidates.csv
    decoded_candidates/ (only if a standard decompressor succeeds)

This is a format-identification aid, not a decoder for proprietary formats.
It never changes original APK resources. A protobuf-looking byte stream is
reported as a heuristic candidate only, not proof that the file is protobuf.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import hashlib
import json
import lzma
import math
import re
import statistics
import zlib
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_rel(value: str) -> str:
    return (value or "").strip().replace("\\", "/").lstrip("./")


def resolve_asset(assets_root: Path, inventory_path: str, resource_file: str) -> Path:
    """Resolve paths recorded in Windows or POSIX inventory CSVs."""
    candidates: list[Path] = []
    for raw in (inventory_path, resource_file):
        rel = norm_rel(raw)
        if not rel:
            continue
        if rel.startswith("assets/"):
            rel = rel[len("assets/"):]
        p = Path(rel)
        candidates.append(assets_root / p)
        candidates.append(assets_root / p.name)
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if p.is_file():
            return p
    return candidates[0] if candidates else root / "__missing__"


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def printable_strings(data: bytes, limit: int = 12) -> list[str]:
    out: list[str] = []
    for match in PRINTABLE_RE.finditer(data):
        try:
            s = match.group(0).decode("ascii")
        except UnicodeDecodeError:
            continue
        out.append(s[:160])
        if len(out) >= limit:
            break
    return out


def identify_magic(data: bytes) -> list[str]:
    tests = [
        (b"\x89PNG\r\n\x1a\n", "PNG"),
        (b"\xff\xd8\xff", "JPEG"),
        (b"PK\x03\x04", "ZIP"),
        (b"\x1f\x8b", "GZIP"),
        (b"SQLite format 3\x00", "SQLite"),
        (b"OggS", "OGG"),
        (b"RIFF", "RIFF"),
        (b"FWS", "SWF-uncompressed"),
        (b"CWS", "SWF-zlib"),
        (b"ZWS", "SWF-LZMA"),
        (b"<?xml", "XML"),
        (b"{", "JSON-like-leading-brace"),
        (b"[", "JSON-like-leading-bracket"),
    ]
    found = [label for prefix, label in tests if data.startswith(prefix)]
    if not found and len(data) >= 2 and data[0] == 0x78 and ((data[0] << 8) + data[1]) % 31 == 0:
        found.append("zlib-header-likely")
    return found or ["unknown"]


def try_decompress(data: bytes) -> tuple[str, bytes] | None:
    attempts = [
        ("gzip", lambda: zlib.decompress(data, 16 + zlib.MAX_WBITS)),
        ("zlib", lambda: zlib.decompress(data)),
        ("raw-deflate", lambda: zlib.decompress(data, -zlib.MAX_WBITS)),
        ("bz2", lambda: bz2.decompress(data)),
        ("lzma-alone-or-xz", lambda: lzma.decompress(data)),
    ]
    for name, fn in attempts:
        try:
            result = fn()
        except Exception:
            continue
        if result and len(result) <= 64 * 1024 * 1024:
            return name, result
    return None


def read_varint(data: bytes, pos: int) -> tuple[int, int] | None:
    value = 0
    shift = 0
    while pos < len(data) and shift <= 63:
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, pos
        shift += 7
    return None


def protobuf_wire_probe(data: bytes) -> tuple[bool, str, list[str]]:
    """Best-effort protobuf wire-format parser; success is only heuristic."""
    pos = 0
    fields: list[str] = []
    field_count = 0
    while pos < len(data):
        key_res = read_varint(data, pos)
        if key_res is None:
            return False, "invalid_key_varint", fields
        key, pos = key_res
        field_no, wire = key >> 3, key & 7
        if field_no == 0 or wire not in (0, 1, 2, 5):
            return False, "invalid_field_or_wire_type", fields
        field_count += 1
        if wire == 0:
            val = read_varint(data, pos)
            if val is None:
                return False, "truncated_varint", fields
            value, pos = val
            detail = f"f{field_no}:varint={value}"
        elif wire == 1:
            if pos + 8 > len(data):
                return False, "truncated_fixed64", fields
            detail = f"f{field_no}:fixed64"
            pos += 8
        elif wire == 5:
            if pos + 4 > len(data):
                return False, "truncated_fixed32", fields
            detail = f"f{field_no}:fixed32"
            pos += 4
        else:
            ln = read_varint(data, pos)
            if ln is None:
                return False, "truncated_length", fields
            length, pos = ln
            if length > len(data) - pos:
                return False, "length_exceeds_remaining", fields
            chunk = data[pos:pos + length]
            pos += length
            strings = printable_strings(chunk, limit=1)
            suffix = f":text={strings[0][:48]}" if strings else f":bytes={length}"
            detail = f"f{field_no}:len={length}{suffix}"
        if len(fields) < 20:
            fields.append(detail)
        if field_count > 5000:
            return False, "field_count_limit", fields
    plausible = field_count > 0 and (field_count >= 2 or len(data) <= 16)
    return plausible, f"wire_parse_ok_fields_{field_count}" if plausible else "wire_parse_weak", fields


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matches", default="legacy_item_comp_matches.csv")
    ap.add_argument("--families", default="legacy_item_asset_families.csv")
    ap.add_argument("--assets-dir", default="assets")
    ap.add_argument("--out-dir", default="binary_probe")
    ap.add_argument("--max-files", type=int, default=0, help="Optional limit for a quick test; 0 means all")
    args = ap.parse_args()

    root = Path.cwd()
    assets_root = root / args.assets_dir
    matches = read_csv(root / args.matches)
    families = read_csv(root / args.families)
    out_dir = root / args.out_dir
    decoded_dir = out_dir / "decoded_candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    decoded_dir.mkdir(parents=True, exist_ok=True)
    for old in decoded_dir.glob("*"):
        if old.is_file():
            old.unlink()

    refs: dict[str, dict[str, Any]] = {}

    def add_ref(kind: str, logical_key: str, file_name: str, inventory_path: str,
                item_id: str, item_title: str, item_type: str) -> None:
        file_name = (file_name or "").strip()
        if not file_name.lower().endswith(".bin"):
            return
        path = resolve_asset(assets_root, inventory_path, file_name)
        key = str(path.resolve()) if path.exists() else str(path)
        row = refs.setdefault(key, {
            "path": path,
            "resource_file": file_name,
            "component_kinds": set(),
            "logical_keys": set(),
            "item_ids": set(),
            "item_titles": set(),
            "item_types": set(),
            "references": 0,
        })
        row["component_kinds"].add(kind)
        if logical_key:
            row["logical_keys"].add(logical_key)
        if item_id:
            row["item_ids"].add(item_id)
        if item_title:
            row["item_titles"].add(item_title)
        if item_type:
            row["item_types"].add(item_type)
        row["references"] += 1

    for row in families:
        add_ref(
            row.get("component_kind", ""), row.get("component_key", ""),
            row.get("resource_file", ""), row.get("inventory_path", ""),
            row.get("item_id", ""), row.get("item_title", ""), row.get("item_type", ""),
        )
    for row in matches:
        add_ref(
            "comp", row.get("matched_logical_key", ""),
            row.get("composition_file", ""), row.get("inventory_path", ""),
            row.get("item_id", ""), row.get("item_title", ""), row.get("item_type", ""),
        )

    all_refs = list(refs.values())
    if args.max_files > 0:
        all_refs = all_refs[:args.max_files]

    output_rows: list[dict[str, Any]] = []
    protobuf_rows: list[dict[str, Any]] = []
    kind_counts: Counter[str] = Counter()
    magic_counts: Counter[str] = Counter()
    size_by_kind: dict[str, list[int]] = defaultdict(list)
    decompressed_count = 0
    missing_count = 0
    decoded_written = 0

    for idx, ref in enumerate(all_refs, 1):
        path: Path = ref["path"]
        kinds = sorted(ref["component_kinds"])
        for kind in kinds:
            kind_counts[kind] += 1
        base = {
            "resource_file": ref["resource_file"],
            "component_kinds": ";".join(kinds),
            "logical_keys": ";".join(sorted(ref["logical_keys"])[:30]),
            "item_ids": ";".join(sorted(ref["item_ids"])[:30]),
            "item_titles": ";".join(sorted(ref["item_titles"])[:20]),
            "item_types": ";".join(sorted(ref["item_types"])),
            "reference_count": ref["references"],
            "local_path": str(path),
            "exists": path.is_file(),
        }
        if not path.is_file():
            missing_count += 1
            output_rows.append({**base, "size_bytes": "", "sha256": "", "entropy_bits_per_byte": "",
                                "magic": "missing", "first_64_hex": "", "printable_strings": "",
                                "decompression": "not_attempted", "decoded_size": "",
                                "protobuf_wire_candidate": "no", "protobuf_probe": "missing"})
            continue

        data = path.read_bytes()
        size = len(data)
        for kind in kinds:
            size_by_kind[kind].append(size)
        magic = identify_magic(data)
        for label in magic:
            magic_counts[label] += 1
        ent = entropy(data)
        strings = printable_strings(data)
        decomp = try_decompress(data)
        dec_name = "none"
        dec_size: int | str = ""
        if decomp:
            dec_name, decoded = decomp
            dec_size = len(decoded)
            decompressed_count += 1
            out_name = f"{idx:05d}_{path.stem}_{dec_name}.bin"
            (decoded_dir / out_name).write_bytes(decoded)
            decoded_written += 1
        else:
            decoded = data

        pb_ok, pb_status, pb_fields = protobuf_wire_probe(data)
        if pb_ok:
            protobuf_rows.append({**base, "size_bytes": size, "probe_status": pb_status,
                                  "field_examples": " | ".join(pb_fields)})
        output_rows.append({
            **base,
            "size_bytes": size,
            "sha256": hashlib.sha256(data).hexdigest(),
            "entropy_bits_per_byte": round(ent, 4),
            "magic": ";".join(magic),
            "first_64_hex": data[:64].hex(" "),
            "printable_strings": " | ".join(strings),
            "decompression": dec_name,
            "decoded_size": dec_size,
            "protobuf_wire_candidate": "possible" if pb_ok else "no",
            "protobuf_probe": pb_status,
        })
        if decomp and decoded:
            # Include a compact text preview if the decompressed result is readable.
            try:
                text_preview = decoded[:300].decode("utf-8")
                if text_preview and sum(ch.isprintable() or ch in "\r\n\t" for ch in text_preview) / len(text_preview) > 0.85:
                    output_rows[-1]["decoded_text_preview"] = text_preview.replace("\n", "\\n")
            except UnicodeDecodeError:
                pass

    csv_path = out_dir / "binary_resource_probe.csv"
    fieldnames = list(output_rows[0].keys()) if output_rows else ["resource_file", "exists"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(output_rows)

    pb_path = out_dir / "protobuf_wire_candidates.csv"
    pb_fields = list(protobuf_rows[0].keys()) if protobuf_rows else ["resource_file", "probe_status", "field_examples"]
    with pb_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pb_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(protobuf_rows)

    def quant(values: list[int]) -> dict[str, Any]:
        if not values:
            return {"count": 0}
        s = sorted(values)
        return {"count": len(s), "min": s[0], "median": statistics.median(s), "max": s[-1]}

    summary = {
        "input_matches_csv_rows": len(matches),
        "input_families_csv_rows": len(families),
        "unique_binary_resources_probed": len(all_refs),
        "missing_binary_resources": missing_count,
        "standard_decompression_successes": decompressed_count,
        "decoded_files_written": decoded_written,
        "protobuf_wire_heuristic_candidates": len(protobuf_rows),
        "component_kind_resource_counts": dict(kind_counts),
        "magic_counts": dict(magic_counts),
        "size_by_component_kind": {k: quant(v) for k, v in sorted(size_by_kind.items())},
        "caution": "A successful decompression identifies a standard wrapper only. A valid protobuf-wire parse is a heuristic and does not prove the resource schema. Unknown files may use a custom format or encryption.",
        "outputs": [str(csv_path.relative_to(root)), str(pb_path.relative_to(root)), str((out_dir / "binary_probe_summary.json").relative_to(root))],
    }
    (out_dir / "binary_probe_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Finished. Binary resource probe completed.")
    print(f"  Unique binaries: {len(all_refs)}")
    print(f"  Missing: {missing_count}")
    print(f"  Standard decompression successes: {decompressed_count}")
    print(f"  Protobuf-wire heuristic candidates: {len(protobuf_rows)}")
    print(f"  Results: {out_dir}")


if __name__ == "__main__":
    main()

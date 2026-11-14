#!/usr/bin/env python3
"""Build a local visual review gallery for APK assets linked to social Zombie Farm items.

Run from the root of the unpacked Zombie Castaways APK GitHub repository:
    py make_zombifarm_visual_review.py

Expected inputs in the repository root:
    legacy_item_comp_matches.csv
    legacy_item_asset_families.csv
    assets/   (the unpacked APK resources)

Outputs:
    legacy_visual_review.html
    legacy_visual_review.json
    legacy_visual_review_stats.json

The gallery groups by APK composition and shows PNG frames found in the family CSV.
It does not decode BIN composition data or claim that Castaways art is identical to
social Zombie Farm art. It is an inspection aid only.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Не найден файл: {path}\nПроверь, что скрипт запущен из корня репозитория и CSV лежат рядом.")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_asset_path(value: str) -> str:
    value = (value or "").strip().replace("\\", "/").lstrip("/")
    if value.casefold().startswith("assets/"):
        value = value[7:]
    return value


def natural_key(value: str) -> list[Any]:
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", value)]


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matches", default="legacy_item_comp_matches.csv")
    ap.add_argument("--families", default="legacy_item_asset_families.csv")
    ap.add_argument("--assets-dir", default="assets")
    ap.add_argument("--output-dir", default=".")
    args = ap.parse_args()

    root = Path.cwd()
    matches_path = Path(args.matches)
    families_path = Path(args.families)
    assets_dir = Path(args.assets_dir)
    out_dir = Path(args.output_dir)
    if not matches_path.is_absolute(): matches_path = root / matches_path
    if not families_path.is_absolute(): families_path = root / families_path
    if not assets_dir.is_absolute(): assets_dir = root / assets_dir
    if not out_dir.is_absolute(): out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    matches = read_csv(matches_path)
    families = read_csv(families_path)
    if not matches:
        raise SystemExit("CSV сопоставлений пуст. Сначала исправь запуск analyze_zombifarm_overlap_v2.py.")

    groups: dict[str, dict[str, Any]] = {}
    for r in matches:
        comp = (r.get("matched_logical_key") or "").strip()
        if not comp:
            continue
        g = groups.setdefault(comp, {
            "composition_key": comp,
            "composition_file": norm_asset_path(r.get("composition_file", "")),
            "composition_size_bytes": r.get("composition_size_bytes", ""),
            "legacy_items": {},
            "frames": {},
            "components": {},
        })
        item_key = (r.get("item_id", ""), r.get("objAnim", ""), r.get("match_method", ""))
        g["legacy_items"][item_key] = {
            "item_id": r.get("item_id", ""),
            "item_type": r.get("item_type", ""),
            "item_title": r.get("item_title", ""),
            "objAnim": r.get("objAnim", ""),
            "match_method": r.get("match_method", ""),
            "evidence_level": r.get("evidence_level", ""),
        }

    for r in families:
        comp = (r.get("composition_key") or "").strip()
        if comp not in groups:
            continue
        kind = (r.get("component_kind") or "").strip()
        logical_key = (r.get("component_key") or "").strip()
        asset = norm_asset_path(r.get("resource_file", ""))
        if not asset:
            continue
        row = {
            "kind": kind,
            "logical_key": logical_key,
            "file": asset,
            "size_bytes": r.get("size_bytes", ""),
            "exists": (assets_dir / asset).is_file(),
        }
        dedup_key = (kind, logical_key, asset)
        groups[comp]["components"][dedup_key] = row
        if kind == "anim" and Path(asset).suffix.casefold() == ".png":
            groups[comp]["frames"][asset] = {
                "logical_key": logical_key,
                "file": asset,
                "size_bytes": r.get("size_bytes", ""),
                "exists": (assets_dir / asset).is_file(),
            }

    output_groups = []
    item_types = Counter()
    total_frame_refs = 0
    missing_frames = 0
    missing_comp_files = 0
    component_kinds = Counter()
    unique_item_ids: set[str] = set()
    unique_obj_anim_values: set[str] = set()
    distinct_png_files: set[str] = set()
    match_method_counts = Counter((r.get("match_method") or "") for r in matches)
    for r in matches:
        if r.get("item_id"):
            unique_item_ids.add(r["item_id"])
        if r.get("objAnim"):
            unique_obj_anim_values.add(r["objAnim"])

    for comp_key, g in groups.items():
        legacy_items = sorted(g["legacy_items"].values(), key=lambda x: (x["item_type"], x["item_title"], x["item_id"], x["objAnim"]))
        frames = sorted(g["frames"].values(), key=lambda x: natural_key(x["logical_key"]))
        components = sorted(g["components"].values(), key=lambda x: (x["kind"], natural_key(x["logical_key"])))
        types = sorted({x["item_type"] for x in legacy_items if x["item_type"]})
        for t in types: item_types[t] += 1
        for c in components: component_kinds[c["kind"]] += 1
        total_frame_refs += len(frames)
        distinct_png_files.update(f["file"] for f in frames)
        missing_frames += sum(1 for f in frames if not f["exists"])
        comp_exists = (assets_dir / g["composition_file"]).is_file() if g["composition_file"] else False
        if not comp_exists: missing_comp_files += 1
        output_groups.append({
            "composition_key": comp_key,
            "composition_file": g["composition_file"],
            "composition_size_bytes": g["composition_size_bytes"],
            "composition_exists": comp_exists,
            "item_types": types,
            "legacy_items": legacy_items,
            "frames": frames,
            "components": components,
        })

    output_groups.sort(key=lambda g: (g["item_types"][0] if g["item_types"] else "", g["composition_key"].casefold()))
    phaser_index = {
        "schema": "zombifarm-asset-review-candidate-v1",
        "notice": "Name-based candidate links only. Castaways art is not confirmed identical to social Zombie Farm art. BIN composition files have not been decoded.",
        "source_matches_csv": matches_path.name,
        "source_families_csv": families_path.name,
        "assets_directory": assets_dir.name,
        "compositions": output_groups,
    }
    json_path = out_dir / "legacy_visual_review.json"
    json_path.write_text(json.dumps(phaser_index, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "match_csv_rows": len(matches),
        "family_csv_rows": len(families),
        "unique_compositions": len(output_groups),
        "unique_item_ids_in_match_csv": len(unique_item_ids),
        "unique_objAnim_values_in_match_csv": len(unique_obj_anim_values),
        "unique_legacy_item_refs": sum(len(g["legacy_items"]) for g in output_groups),
        "match_method_counts_from_csv_rows": dict(match_method_counts),
        "png_frame_references": total_frame_refs,
        "distinct_png_files": len(distinct_png_files),
        "missing_png_frames": missing_frames,
        "composition_files_missing_on_disk": missing_comp_files,
        "component_kind_rows": dict(component_kinds),
        "composition_groups_by_item_type": dict(item_types),
        "note": "Missing-on-disk checks are relative to --assets-dir. This summary does not confirm visual identity or decode BIN files.",
    }
    (out_dir / "legacy_visual_review_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    cards = []
    for g in output_groups:
        item_tags = []
        for item in g["legacy_items"]:
            item_tags.append(
                f'<span class="tag">{esc(item["item_title"])} · {esc(item["item_id"])} · {esc(item["objAnim"])}</span>'
            )
        type_text = ", ".join(g["item_types"])
        frames_html = []
        for frame in g["frames"]:
            rel = "../" + frame["file"] if out_dir != root else frame["file"]
            if frame["exists"]:
                frames_html.append(
                    f'<a class="frame" href="{esc(rel)}" target="_blank" title="{esc(frame["logical_key"])}">'
                    f'<img loading="lazy" src="{esc(rel)}" alt="{esc(frame["logical_key"])}">'
                    f'<small>{esc(frame["logical_key"])}</small></a>'
                )
            else:
                frames_html.append(f'<div class="frame missing"><b>PNG не найден</b><small>{esc(frame["file"])}</small></div>')
        if not frames_html:
            frames_html.append('<div class="no-frames">PNG-кадры для этой композиции в families CSV не найдены.</div>')
        kinds = Counter(c["kind"] for c in g["components"])
        kind_text = " · ".join(f"{k}: {v}" for k, v in sorted(kinds.items()))
        missing_badge = '' if g["composition_exists"] else '<span class="warning">BIN не найден локально</span>'
        search_blob = " ".join([g["composition_key"], type_text] + [x["item_id"] + " " + x["item_title"] + " " + x["objAnim"] for x in g["legacy_items"]]).casefold()
        cards.append(
            f'<article class="card" data-types="{esc(" ".join(g["item_types"]))}" data-search="{esc(search_blob)}">'
            f'<header><div><h2>{esc(g["composition_key"])}</h2><div class="meta">Типы: {esc(type_text or "не определён")} · {len(g["legacy_items"])} связей · {len(g["frames"])} PNG</div></div>{missing_badge}</header>'
            f'<div class="tags">{"".join(item_tags)}</div>'
            f'<div class="frames">{"".join(frames_html)}</div>'
            f'<details><summary>Технические компоненты ({len(g["components"])})</summary><p>{esc(kind_text)}</p><ul>'
            + "".join(f'<li><code>{esc(c["kind"])} · {esc(c["logical_key"])}</code> — {esc(c["file"])} ({esc(c["size_bytes"])} bytes) {"✓" if c["exists"] else "—"}</li>' for c in g["components"])
            + '</ul></details></article>'
        )

    all_types = sorted({t for g in output_groups for t in g["item_types"]})
    select_options = '<option value="">Все типы объектов</option>' + ''.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in all_types)
    html_doc = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zombie Farm — галерея кандидатов графики</title>
<style>
:root{{color-scheme:light dark;font-family:Segoe UI,Arial,sans-serif}}body{{margin:0;padding:24px;background:#17191d;color:#f1f3f5}}h1{{margin:0 0 8px}}.notice{{background:#3b2b13;border:1px solid #8b6329;padding:12px 14px;border-radius:10px;margin:14px 0 18px;color:#ffe4b2}}.toolbar{{display:flex;gap:10px;flex-wrap:wrap;position:sticky;top:0;background:#17191d;padding:12px 0;z-index:2}}input,select{{padding:10px 12px;border-radius:8px;border:1px solid #555;background:#252a31;color:#fff;min-width:210px}}#count{{color:#aeb6c2;align-self:center}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}}.card{{background:#22262d;border:1px solid #3a414a;border-radius:12px;padding:14px;min-width:0}}header{{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}}h2{{font-size:17px;margin:0 0 5px;overflow-wrap:anywhere}}.meta,small{{color:#aeb6c2;font-size:12px}}.tags{{display:flex;gap:5px;flex-wrap:wrap;margin:10px 0}}.tag{{font-size:11px;border:1px solid #4b5663;border-radius:6px;padding:4px 6px;color:#d8e0e8}}.frames{{display:grid;grid-template-columns:repeat(auto-fill,minmax(105px,1fr));gap:8px}}.frame{{display:flex;flex-direction:column;gap:5px;text-decoration:none;color:#dce2e8;background:#15181c;padding:6px;border-radius:8px;min-width:0}}.frame img{{width:100%;height:110px;object-fit:contain;background:#fff;border-radius:5px}}.frame small{{overflow-wrap:anywhere}}.missing,.no-frames{{padding:12px;color:#ffc5a8;background:#392721;border-radius:8px;overflow-wrap:anywhere}}.warning{{color:#ffcc80;font-size:11px}}details{{margin-top:12px;color:#c5ccd4}}summary{{cursor:pointer}}li{{font-size:12px;margin:4px 0;overflow-wrap:anywhere}}code{{color:#b7d5ff}}.hidden{{display:none!important}}
</style></head><body>
<h1>Галерея кандидатов графики — социальная «Зомби Ферма»</h1>
<div>Композиции: {len(output_groups)} · связи из CSV: {len(matches)} · строки компонентов: {len(families)}</div>
<div class="notice"><b>Важно:</b> это кандидаты из APK Zombie Castaways, подобранные по именам ресурсов. Совпадение имени не доказывает, что изображение идентично графике социальной версии. Сверяй силуэт, цвета, ракурс и детали со старыми скриншотами. BIN-файлы здесь не декодируются.</div>
<div class="toolbar"><input id="q" placeholder="Поиск: Вавилон, B_BABEL, b_babel…"><select id="type">{select_options}</select><span id="count"></span></div>
<div class="grid" id="grid">{"".join(cards)}</div>
<script>
const q=document.getElementById('q'),type=document.getElementById('type'),cards=[...document.querySelectorAll('.card')],count=document.getElementById('count');
function apply(){{const s=q.value.toLocaleLowerCase(),t=type.value;let n=0;for(const c of cards){{const ok=(!s||c.dataset.search.includes(s))&&(!t||c.dataset.types.split(' ').includes(t));c.classList.toggle('hidden',!ok);if(ok)n++}}count.textContent=`Показано: ${{n}} из ${{cards.length}}`;}}
q.addEventListener('input',apply);type.addEventListener('change',apply);apply();
</script></body></html>'''
    html_path = out_dir / "legacy_visual_review.html"
    html_path.write_text(html_doc, encoding="utf-8")

    print("Готово. Созданы файлы:")
    print(f"  {html_path}")
    print(f"  {json_path}")
    print(f"  {out_dir / 'legacy_visual_review_stats.json'}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

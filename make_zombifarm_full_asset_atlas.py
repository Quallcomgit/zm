#!/usr/bin/env python3
"""Build a searchable atlas of every PNG in an unpacked APK and audit legacy objAnim coverage.

Run from the root of the unpacked APK repository:
    py make_zombifarm_full_asset_atlas.py --items path/to/items.json

Inputs:
    assets/                       PNG resources and assets/desc.txt
    desc.txt                      optional root descriptor
    items.json                    optional original social Zombie Farm catalog
    legacy_item_comp_matches.csv  optional existing name-match table

Outputs:
    full_asset_atlas.html
    full_asset_atlas_manifest.csv
    legacy_asset_coverage.csv     (when items.json is supplied)
    legacy_asset_coverage_summary.json

No third-party Python packages are required. The HTML is self-contained except for
local PNG files; it displays 100 images per page to avoid loading the whole APK at once.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_path(value: str) -> str:
    value = (value or "").strip().replace("\\", "/").lstrip("/")
    if value.casefold().startswith("assets/"):
        value = value[7:]
    return value


def norm_key(value: str) -> str:
    return norm_path(value).casefold()


def relative_url(path: Path, html_dir: Path) -> str:
    rel = os.path.relpath(str(path.resolve()), start=str(html_dir.resolve()))
    return quote(Path(rel).as_posix(), safe="/:@-._~")


def png_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as f:
            head = f.read(24)
        if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            return struct.unpack(">II", head[16:24])
    except OSError:
        pass
    return None, None


def descriptor_png_map(desc_paths: list[Path]) -> tuple[dict[str, list[str]], dict[str, int], set[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    line_counts: dict[str, int] = {}
    all_logical_keys: set[str] = set()
    for desc in desc_paths:
        if not desc.is_file():
            continue
        count = 0
        try:
            with desc.open("r", encoding="utf-8-sig", errors="replace") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or "=" not in line:
                        continue
                    logical, resource = line.split("=", 1)
                    logical = logical.strip()
                    resource = norm_path(resource)
                    if logical:
                        all_logical_keys.add(logical.casefold())
                    if logical and resource.casefold().endswith(".png"):
                        result[norm_key(resource)].append(logical)
                        count += 1
        except OSError:
            continue
        line_counts[str(desc)] = count
    # Deduplicate aliases while preserving order.
    return {k: list(dict.fromkeys(v)) for k, v in result.items()}, line_counts, all_logical_keys


def iter_obj_anim(value: Any) -> list[str]:
    if value is None:
        return []
    vals = value if isinstance(value, list) else [value]
    return [str(v).strip() for v in vals if str(v).strip()]


def load_legacy_items(items_path: Path) -> list[dict[str, Any]]:
    if not items_path.is_file():
        return []
    try:
        data = json.loads(items_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"Не удалось прочитать items JSON: {items_path}\n{exc}")
    if not isinstance(data, list):
        raise SystemExit("Ожидался JSON-массив записей items.json.")
    return data


def item_label(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("title") or "").strip()


def safe_json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets-dir", default="assets")
    ap.add_argument("--items", default="items.json", help="Путь к исходному items.json; можно указать абсолютный путь")
    ap.add_argument("--matches", default="legacy_item_comp_matches.csv")
    ap.add_argument("--desc", action="append", default=[], help="Дополнительный файл desc; параметр можно повторять")
    ap.add_argument("--output-dir", default=".")
    ap.add_argument("--page-size", type=int, default=100)
    args = ap.parse_args()

    root = Path.cwd()
    assets_dir = Path(args.assets_dir)
    items_path = Path(args.items)
    matches_path = Path(args.matches)
    output_dir = Path(args.output_dir)
    for p_name in ("assets_dir", "items_path", "matches_path", "output_dir"):
        p = locals()[p_name]
        if not p.is_absolute():
            locals()[p_name] = root / p
    # Assign explicitly; writes to locals() are not guaranteed to update fast locals.
    assets_dir = assets_dir if assets_dir.is_absolute() else root / assets_dir
    items_path = items_path if items_path.is_absolute() else root / items_path
    matches_path = matches_path if matches_path.is_absolute() else root / matches_path
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not assets_dir.is_dir():
        raise SystemExit(f"Не найдена папка с ресурсами: {assets_dir}")
    page_size = max(20, min(300, args.page_size))

    desc_paths = [assets_dir / "desc.txt", root / "desc.txt"]
    for p in args.desc:
        pp = Path(p)
        desc_paths.append(pp if pp.is_absolute() else root / pp)
    desc_paths = list(dict.fromkeys(desc_paths))
    png_names, descriptor_lines, all_descriptor_keys = descriptor_png_map(desc_paths)

    png_files = sorted((p for p in assets_dir.rglob("*") if p.is_file() and p.suffix.casefold() == ".png"), key=lambda p: p.as_posix().casefold())
    manifest_rows: list[dict[str, Any]] = []
    html_items: list[dict[str, Any]] = []
    for p in png_files:
        rel = p.relative_to(assets_dir).as_posix()
        w, h = png_dimensions(p)
        desc = png_names.get(norm_key(rel), [])
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        row = {
            "file": rel,
            "width": w or "",
            "height": h or "",
            "pixels": (w * h) if w and h else 0,
            "size_bytes": size,
            "descriptor_count": len(desc),
            "descriptor_keys": " | ".join(desc),
        }
        manifest_rows.append(row)
        html_items.append({
            "file": rel,
            "url": relative_url(p, output_dir),
            "width": w,
            "height": h,
            "pixels": row["pixels"],
            "size": size,
            "keys": desc,
            "hasKeys": bool(desc),
            "search": (rel + " " + " ".join(desc)).casefold(),
        })

    manifest_path = output_dir / "full_asset_atlas_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "width", "height", "pixels", "size_bytes", "descriptor_count", "descriptor_keys"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    # Compare original game item references against the existing candidate-link table.
    legacy = load_legacy_items(items_path)
    matches = read_csv(matches_path)
    match_pairs = set()
    match_ids = set()
    for m in matches:
        item_id = str(m.get("item_id") or "").strip()
        anim = str(m.get("objAnim") or "").strip()
        if item_id:
            match_ids.add(item_id)
        if item_id and anim:
            match_pairs.add((item_id, anim))

    coverage_rows: list[dict[str, Any]] = []
    seen = set()
    type_counts = Counter()
    matched_type_counts = Counter()
    for item in legacy:
        anims = iter_obj_anim(item.get("objAnim"))
        if not anims:
            continue
        item_id = str(item.get("id") or "").strip()
        item_type = str(item.get("type") or "").strip()
        label = item_label(item)
        shop_image = str(item.get("shopImage") or item.get("image") or "").strip()
        for anim in anims:
            key = (item_id, item_type, anim)
            if key in seen:
                continue
            seen.add(key)
            # Look for the exact legacy animation name, and for common wrappers/prefixes.
            base = re.sub(r"_\d+$", "", anim)
            wanted = {
                anim.casefold(), f"comp:{anim}".casefold(), f"anim_obj:{anim}".casefold(),
                f"mobj:{anim}".casefold(), f"spr:{anim}".casefold(),
                base.casefold(), f"comp:{base}".casefold(), f"anim_obj:{base}".casefold(),
                f"mobj:{base}".casefold(), f"spr:{base}".casefold(),
            }
            descriptor_hits = sorted(k for k in all_descriptor_keys if k in wanted)
            has_comp_match = (item_id, anim) in match_pairs
            status = "есть в текущей таблице кандидатов" if has_comp_match else "не найдено в текущей таблице кандидатов"
            coverage_rows.append({
                "item_id": item_id,
                "item_type": item_type,
                "item_title": label,
                "objAnim": anim,
                "shopImage": shop_image,
                "candidate_match": "yes" if has_comp_match else "no",
                "candidate_status": status,
                "descriptor_name_match": "yes" if descriptor_hits else "no",
                "descriptor_keys_found": " | ".join(descriptor_hits),
            })
            type_counts[item_type] += 1
            if has_comp_match:
                matched_type_counts[item_type] += 1

    if legacy:
        coverage_path = output_dir / "legacy_asset_coverage.csv"
        with coverage_path.open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["item_id", "item_type", "item_title", "objAnim", "shopImage", "candidate_match", "candidate_status", "descriptor_name_match", "descriptor_keys_found"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(coverage_rows)

    total_bytes = sum(int(r["size_bytes"]) for r in manifest_rows)
    linked_pngs = sum(1 for r in manifest_rows if r["descriptor_count"])
    summary = {
        "png_files_found": len(manifest_rows),
        "png_files_with_descriptor_names": linked_pngs,
        "png_files_without_descriptor_names": len(manifest_rows) - linked_pngs,
        "descriptor_files_scanned": descriptor_lines,
        "total_png_bytes": total_bytes,
        "items_json_loaded": bool(legacy),
        "legacy_objAnim_rows": len(coverage_rows),
        "legacy_objAnim_rows_with_existing_candidate_match": sum(1 for r in coverage_rows if r["candidate_match"] == "yes"),
        "legacy_objAnim_rows_without_existing_candidate_match": sum(1 for r in coverage_rows if r["candidate_match"] == "no"),
        "legacy_objAnim_rows_with_descriptor_name_match": sum(1 for r in coverage_rows if r["descriptor_name_match"] == "yes"),
        "legacy_objAnim_rows_without_descriptor_name_match": sum(1 for r in coverage_rows if r["descriptor_name_match"] == "no"),
        "legacy_rows_by_type": dict(type_counts),
        "candidate_matches_by_type": dict(matched_type_counts),
        "matches_csv_rows": len(matches),
        "caution": "Отсутствие совпадения по имени не доказывает отсутствие изображения: имя в APK могло быть изменено, а PNG может быть не привязан к legacy objAnim.",
    }
    (output_dir / "legacy_asset_coverage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Put large images first; building sprites are generally easier to notice this way.
    html_data = safe_json_script(html_items)
    html_doc = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Полный атлас PNG ресурсов APK — Zombie Farm research</title>
<style>
:root{{color-scheme:dark;font-family:Segoe UI,Arial,sans-serif}}body{{margin:0;padding:22px;background:#17191d;color:#f1f3f5}}
h1{{font-size:24px;margin:0 0 6px}}.note{{color:#c5ccd4;font-size:13px;margin:8px 0 16px;max-width:1100px;line-height:1.5}}
.toolbar{{display:flex;flex-wrap:wrap;gap:9px;align-items:center;position:sticky;top:0;background:#17191d;padding:10px 0;z-index:5}}
input,select,button{{background:#252a31;color:#fff;border:1px solid #505a66;border-radius:8px;padding:9px 11px;font-size:14px}}
input{{min-width:280px;flex:1}}button{{cursor:pointer}}button:disabled{{opacity:.4;cursor:default}}#status{{color:#bdc6d0;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:14px}}
.card{{background:#22262d;border:1px solid #3a414a;border-radius:10px;padding:9px;min-width:0}}
.card img{{display:block;width:100%;height:175px;object-fit:contain;background:#fff;border-radius:6px}}
.file{{font-size:12px;overflow-wrap:anywhere;color:#b9d8ff;margin:7px 0 4px}}
.meta{{font-size:11px;color:#aeb6c2}}details{{font-size:11px;margin-top:7px;color:#d3dbe3}}summary{{cursor:pointer}}.keys{{overflow-wrap:anywhere;margin:5px 0 0;padding-left:17px}}
.pager{{display:flex;gap:8px;align-items:center;justify-content:center;margin:16px 0 30px}}
.empty{{padding:30px;text-align:center;color:#c5ccd4}}
</style></head><body>
<h1>Полный атлас PNG из APK</h1>
<div class="note">Здесь собраны все PNG из папки assets, а не только кадры из 195 уже сопоставленных композиций. Имена под картинками взяты из desc.txt, когда для файла есть такая запись. Картинка без имени в desc.txt всё равно остаётся в атласе. Это вспомогательный визуальный поиск: совпадение картинки с социальной «Зомби Фермой» нужно подтверждать отдельно.</div>
<div class="toolbar">
<input id="q" placeholder="Поиск по имени файла или логическому имени…">
<select id="minEdge"><option value="0">Любой размер</option><option value="64">Минимум 64 px</option><option value="128">Минимум 128 px</option><option value="256">Минимум 256 px</option><option value="512">Минимум 512 px</option></select>
<select id="named"><option value="all">Все PNG</option><option value="yes">С именами из desc.txt</option><option value="no">Без имени в desc.txt</option></select>
<select id="sort"><option value="area">Сначала крупные</option><option value="name">По имени файла</option><option value="size">По размеру файла</option></select>
<span id="status"></span>
</div>
<div id="grid" class="grid"></div>
<div class="pager"><button id="prev">← Назад</button><span id="pageInfo"></span><button id="next">Дальше →</button></div>
<script>
const ITEMS={html_data};
const PAGE_SIZE={page_size};
const q=document.getElementById('q'), minEdge=document.getElementById('minEdge'), named=document.getElementById('named'), sort=document.getElementById('sort');
const grid=document.getElementById('grid'), status=document.getElementById('status'), pageInfo=document.getElementById('pageInfo');
const prev=document.getElementById('prev'), next=document.getElementById('next');
let page=0, filtered=[];
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function apply(){{
 const term=q.value.trim().toLocaleLowerCase(); const edge=Number(minEdge.value); const n=named.value;
 filtered=ITEMS.filter(x=>(!term||x.search.includes(term))&&Math.min(x.width||0,x.height||0)>=edge&&(n==='all'||(n==='yes'?x.hasKeys:!x.hasKeys)));
 const mode=sort.value;
 filtered.sort((a,b)=>mode==='name'?a.file.localeCompare(b.file):mode==='size'?b.size-a.size:b.pixels-a.pixels);
 page=0; render();
}}
function render(){{
 const pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE)); page=Math.min(page,pages-1);
 const slice=filtered.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE); grid.innerHTML='';
 if(!slice.length){{grid.innerHTML='<div class="empty">Ничего не найдено. Попробуй изменить поиск или фильтр.</div>';}}
 for(const x of slice){{
  const card=document.createElement('article'); card.className='card';
  const link=document.createElement('a'); link.href=x.url; link.target='_blank'; link.rel='noopener';
  const img=document.createElement('img'); img.loading='lazy'; img.src=x.url; img.alt=x.file; link.appendChild(img); card.appendChild(link);
  const file=document.createElement('div'); file.className='file'; file.textContent=x.file; card.appendChild(file);
  const meta=document.createElement('div'); meta.className='meta'; meta.textContent=`${{x.width??'?'}}×${{x.height??'?'}} px · ${{(x.size/1024).toFixed(1)}} KB · имён: ${{x.keys.length}}`; card.appendChild(meta);
  if(x.keys.length){{const det=document.createElement('details'); const sum=document.createElement('summary'); sum.textContent='Логические имена'; det.appendChild(sum); const ul=document.createElement('ul'); ul.className='keys'; for(const k of x.keys){{const li=document.createElement('li');li.textContent=k;ul.appendChild(li);}} det.appendChild(ul);card.appendChild(det);}}
  grid.appendChild(card);
 }}
 status.textContent=`Показано ${{filtered.length? page*PAGE_SIZE+1:0}}–${{Math.min((page+1)*PAGE_SIZE,filtered.length)}} из ${{filtered.length}}; всего PNG: ${{ITEMS.length}}`;
 pageInfo.textContent=`Страница ${{page+1}} из ${{pages}}`; prev.disabled=page===0; next.disabled=page>=pages-1;
}}
[q,minEdge,named,sort].forEach(el=>el.addEventListener(el===q?'input':'change',apply));
prev.addEventListener('click',()=>{{page=Math.max(0,page-1);render();}}); next.addEventListener('click',()=>{{page++;render();}});
apply();
</script></body></html>'''
    (output_dir / "full_asset_atlas.html").write_text(html_doc, encoding="utf-8")

    print(f"PNG найдено: {len(manifest_rows)}")
    print(f"PNG с именами из desc.txt: {linked_pngs}; без имён: {len(manifest_rows)-linked_pngs}")
    print(f"HTML: {output_dir / 'full_asset_atlas.html'}")
    print(f"CSV:  {manifest_path}")
    if legacy:
        print(f"Объектных objAnim ссылок в items.json: {len(coverage_rows)}")
        print(f"Сопоставлено текущей таблицей: {summary['legacy_objAnim_rows_with_existing_candidate_match']}")
        print(f"Пока без сопоставления: {summary['legacy_objAnim_rows_without_existing_candidate_match']}")
        print(f"CSV покрытия: {output_dir / 'legacy_asset_coverage.csv'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build normalized research exports for the original social/VK Zombie Farm.
Only standard library. Exact-duplicate removal only; source files are never modified.
"""
from __future__ import annotations
import argparse, csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict


def read_csv(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=';', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def dump_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def j(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return value


def item_title(x):
    return x.get('name') or x.get('title') or x.get('id') or ''


def item_anim(x):
    a = x.get('objAnim')
    if isinstance(a, list): return '|'.join(str(v) for v in a)
    return str(a or '')


def resolve_path(path, manifest):
    if not path or not isinstance(path, str): return None
    options = [path]
    if not path.startswith('icons/'): options.append('icons/' + path)
    if not path.startswith('res/'): options.append('res/' + path)
    for opt in options:
        if opt in manifest: return manifest[opt]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--items', default='items.json')
    ap.add_argument('--assets', default='assets.csv')
    ap.add_argument('--relations', default='item_relations.csv')
    ap.add_argument('--locations', default='locations.csv')
    ap.add_argument('--out', default='zombifarm_original_catalog_v1')
    args = ap.parse_args()

    src_items = Path(args.items)
    src_assets = Path(args.assets)
    src_rel = Path(args.relations)
    src_loc = Path(args.locations)
    for p in (src_items, src_assets, src_rel, src_loc):
        if not p.is_file(): raise SystemExit(f'Missing required input: {p}')

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    raw = json.loads(src_items.read_text(encoding='utf-8'))
    if not isinstance(raw, list): raise SystemExit('items.json root is not an array')
    seen = set(); unique = []
    for x in raw:
        if not isinstance(x, dict): continue
        sig = json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if sig not in seen:
            seen.add(sig); unique.append(x)
    ids = [x.get('id') for x in unique]
    if len(ids) != len(set(ids)):
        raise SystemExit('Distinct records share an ID; stopping to avoid accidental overwrite.')

    assets = read_csv(src_assets)
    manifest = {}
    for a in assets:
        p = a.get('path')
        if p and p not in manifest: manifest[p] = a

    # Core full normalized item index, with complex structures kept losslessly in JSON columns.
    flat_fields = [
        'id','type','name','title','level','shopImage','resolved_shop_asset','shop_asset_sha1','shop_asset_size',
        'image','resolved_image_asset','storageImage','resolved_storage_asset','objType','objAnim',
        'buyCoins','saleBuyCoins','buyCash','originalBuyReal','sellCoins','openCash','xp','gift',
        'harvestTime','fruitingTime','fruitingCount','cookingTime','storageItem','material','materialCount',
        'box','wild','multiPlace','moved','movedOnlyLocation','dynamicLight','important','subType',
        'hint','description','upgrades_json','crafts_json','games_json','travels_json','requirements_json',
        'ingredients_json','result','fields_json'
    ]
    all_flat = []
    for x in unique:
        shop = resolve_path(x.get('shopImage'), manifest)
        image_ref = resolve_path(x.get('image'), manifest)
        storage = resolve_path(x.get('storageImage'), manifest)
        row = {k: x.get(k, '') for k in flat_fields}
        row.update({
            'name': x.get('name',''), 'title': x.get('title',''),
            'resolved_shop_asset': shop.get('path','') if shop else '',
            'shop_asset_sha1': shop.get('sha1','') if shop else '',
            'shop_asset_size': shop.get('size_bytes','') if shop else '',
            'resolved_image_asset': image_ref.get('path','') if image_ref else '',
            'resolved_storage_asset': storage.get('path','') if storage else '',
            'objAnim': item_anim(x),
            'upgrades_json': j(x.get('upgrades')),
            'crafts_json': j(x.get('crafts')),
            'games_json': j(x.get('games')),
            'travels_json': j(x.get('travels')),
            'requirements_json': j(x.get('requirements')),
            'ingredients_json': j(x.get('ingridients') or x.get('ingredients')),
            'result': j(x.get('result')),
            'fields_json': j({k:v for k,v in x.items() if k not in flat_fields})
        })
        all_flat.append(row)
    write_csv(out/'items_index.csv', all_flat, flat_fields)

    dump_json(out/'items_unique.json', unique)

    # Type summary.
    by_type = defaultdict(list)
    for x in unique: by_type[x.get('type','')].append(x)
    type_rows = []
    raw_type_counts = Counter(x.get('type','') for x in raw if isinstance(x,dict))
    for typ, rows in sorted(by_type.items(), key=lambda kv:(-len(kv[1]), kv[0])):
        type_rows.append({'type':typ,'unique_records':len(rows),'raw_records':raw_type_counts[typ],
                          'records_with_name':sum(bool(x.get('name') or x.get('title')) for x in rows),
                          'records_with_shopImage':sum(bool(x.get('shopImage')) for x in rows),
                          'records_with_objAnim':sum(bool(x.get('objAnim')) for x in rows)})
    write_csv(out/'type_summary.csv', type_rows)

    # Specialized object categories.
    def export_type(typ, filename):
        rows=[]
        for x in by_type.get(typ,[]):
            sp=resolve_path(x.get('shopImage'),manifest)
            rows.append({
                'id':x.get('id',''), 'name':item_title(x), 'level':x.get('level',''),
                'shopImage':x.get('shopImage',''), 'manifest_path':sp.get('path','') if sp else '',
                'sha1':sp.get('sha1','') if sp else '', 'size_bytes':sp.get('size_bytes','') if sp else '',
                'objType':x.get('objType',''), 'objAnim':item_anim(x),
                'buyCoins':x.get('buyCoins',''), 'saleBuyCoins':x.get('saleBuyCoins',''),
                'buyCash':x.get('buyCash',''), 'sellCoins':x.get('sellCoins',''), 'openCash':x.get('openCash',''),
                'xp':x.get('xp',''), 'harvestTime':x.get('harvestTime',''), 'fruitingTime':x.get('fruitingTime',''),
                'fruitingCount':x.get('fruitingCount',''), 'storageItem':x.get('storageItem',''),
                'material':x.get('material',''), 'materialCount':x.get('materialCount',''),
                'hint':x.get('hint',''), 'description':x.get('description',''),
                'upgrades_json':j(x.get('upgrades')), 'crafts_json':j(x.get('crafts')),
                'games_json':j(x.get('games')), 'travels_json':j(x.get('travels')),
                'fields_json':j(x)
            })
        fields=list(rows[0].keys()) if rows else ['id','name']
        write_csv(out/filename,rows,fields)
        return len(rows)

    category_files = {
        'building':'buildings.csv','seed':'seeds.csv','recipe':'recipes.csv',
        'decoration':'decorations.csv','woodTree':'wood_trees.csv','fruitTree':'fruit_trees.csv',
        'stone':'stones.csv','pier':'piers.csv','location':'locations_original.csv',
        'explorationLocation':'exploration_locations.csv','pathPart':'path_parts.csv'
    }
    category_counts={}
    for typ,fn in category_files.items(): category_counts[typ]=export_type(typ,fn)

    # Ingredient and recipe resolution against unique item IDs (supports @ prefix).
    item_by_id={x.get('id'):x for x in unique}
    def resolve_id(ref):
        if not isinstance(ref,str): return ('','')
        key=ref[1:] if ref.startswith('@') else ref
        hit=item_by_id.get(key)
        return (key, item_title(hit) if hit else '')
    recipe_rows=[]
    for x in by_type.get('recipe',[]):
        ingredients=x.get('ingridients') or x.get('ingredients') or []
        enriched=[]
        for ing in ingredients if isinstance(ingredients,list) else []:
            iid,iname=resolve_id(ing.get('item'))
            enriched.append({'id':iid,'name':iname,'count':ing.get('count'),'raw':ing})
        rid,rname=resolve_id(x.get('result'))
        recipe_rows.append({
            'id':x.get('id',''),'name':item_title(x),'description':x.get('description',''),
            'cookingTime':x.get('cookingTime',''),'ingredients_resolved_json':j(enriched),
            'result_id':rid,'result_name':rname,'result_ref':x.get('result',''),
            'full_recipe_json':j(x)
        })
    write_csv(out/'recipes_resolved.csv',recipe_rows)

    # Manifest references audit over source item references.
    ref_fields=['shopImage','image','storageImage']
    ref_map=defaultdict(lambda:{'item_ids':set(),'item_types':set(),'source_values':set()})
    for x in unique:
        for fld in ref_fields:
            val=x.get(fld)
            if isinstance(val,str) and val:
                rec=ref_map[(fld,val)]
                rec['item_ids'].add(x.get('id',''))
                rec['item_types'].add(x.get('type',''))
                rec['source_values'].add(val)
        # Catch nested prize images (e.g., slots/games) without mistaking ordinary strings for image refs.
        def walk(value, path='$'):
            if isinstance(value,dict):
                for k,v in value.items():
                    p=f'{path}.{k}'
                    if isinstance(v,str) and k.lower().endswith('image') and v and k not in ref_fields:
                        rec=ref_map[(k,v)]; rec['item_ids'].add(x.get('id','')); rec['item_types'].add(x.get('type','')); rec['source_values'].add(v)
                    walk(v,p)
            elif isinstance(value,list):
                for i,v in enumerate(value): walk(v,f'{path}[{i}]')
        walk(x)

    audit=[]
    for (fld,val),info in sorted(ref_map.items()):
        hit=resolve_path(val,manifest)
        audit.append({
            'source_field':fld,'source_value':val,'manifest_status':'FOUND' if hit else 'NOT_FOUND',
            'manifest_path':hit.get('path','') if hit else '',
            'sha1':hit.get('sha1','') if hit else '', 'size_bytes':hit.get('size_bytes','') if hit else '',
            'item_count':len(info['item_ids']),'item_ids':'|'.join(sorted(info['item_ids'])),
            'item_types':'|'.join(sorted(info['item_types']))
        })
    write_csv(out/'asset_reference_audit.csv',audit)

    # Unresolved relation report with source aggregation; unresolved entries can be symbolic runtime groups.
    relations=read_csv(src_rel)
    unresolved=[r for r in relations if str(r.get('target_found','')).lower() not in ('true','1','yes')]
    rel_groups=defaultdict(list)
    for r in unresolved: rel_groups[(r.get('reference',''),r.get('source_type',''),r.get('json_path',''))].append(r)
    unresolved_rows=[]
    for (ref,stype,path), rr in sorted(rel_groups.items()):
        unresolved_rows.append({
            'reference':ref,'source_type':stype,'json_path':path,'occurrences':len(rr),
            'source_ids':'|'.join(sorted({r.get('source_id','') for r in rr}))
        })
    write_csv(out/'relations_unresolved_grouped.csv',unresolved_rows)

    # Original location manifest enriched source.
    loc_rows=read_csv(src_loc)
    write_csv(out/'locations_manifest_audit.csv',loc_rows)

    # High-value verified object facts.
    important_ids=['B_PYRAMID','B_MAYA','B_WHITEHOUSE','B_JAPAN','B_TEMPLE','D_TEMPLE',
                   'B_TOWER','B_WALL','B_WALL_F','B_ROCKET','B_STONEHANGE']
    facts=[]
    for iid in important_ids:
        x=item_by_id.get(iid)
        if not x: continue
        sp=resolve_path(x.get('shopImage'),manifest)
        facts.append({
            'id':iid,'name':item_title(x),'type':x.get('type',''),'level':x.get('level',''),
            'shopImage':x.get('shopImage',''),'manifest_path':sp.get('path','') if sp else '',
            'objAnim':item_anim(x),'buyCoins':x.get('buyCoins',''),'buyCash':x.get('buyCash',''),
            'upgrade_count':len(x.get('upgrades') or []),'craft_count':len(x.get('crafts') or []),
            'travel_count':len(x.get('travels') or []),'hint':x.get('hint',''),
            'upgrades_json':j(x.get('upgrades')),'crafts_json':j(x.get('crafts')),
            'travels_json':j(x.get('travels'))
        })
    write_csv(out/'key_building_facts.csv',facts)

    # Summary and README.
    asset_counts=Counter(r['manifest_status'] for r in audit)
    ref_field_summary={}
    for fld in ref_fields:
        rr=[a for a in audit if a['source_field']==fld]
        ref_field_summary[fld]={'unique_refs':len(rr),'found':sum(a['manifest_status']=='FOUND' for a in rr),'not_found':sum(a['manifest_status']=='NOT_FOUND' for a in rr)}
    summary={
        'source_items_raw':len(raw),'source_items_after_exact_dedupe':len(unique),
        'distinct_ids':len(set(ids)),'exact_duplicates_removed':len(raw)-len(unique),
        'unique_item_types':len(by_type),'assets_manifest_rows':len(assets),'assets_manifest_unique_paths':len(manifest),
        'category_counts':category_counts,'image_reference_summary':ref_field_summary,
        'image_reference_audit_unique_rows':len(audit),
        'item_relations_rows':len(relations),'item_relations_unresolved_rows':len(unresolved),
        'item_relations_unresolved_groups':len(unresolved_rows),
        'source_priority':'items.json and assets.csv are the primary evidence for original social Zombie Farm. Castaways is auxiliary only.',
        'limitations':[
            'assets.csv is an original-game asset manifest (path, SHA-1, size), not the actual SWF/PNG payloads.',
            'A FOUND manifest path proves that the original client manifest lists the resource, not that this export currently contains its bytes.',
            'Exact duplicate removal only; no items with distinct content sharing the same ID were found.'
        ]
    }
    dump_json(out/'catalog_summary.json',summary)

    readme=f'''# Каталог оригинальной социальной «Зомби Фермы» — v1\n\n'''+f'''Этот пакет собран из исходного `items.json`, оригинального манифеста `assets.csv`, `item_relations.csv` и `locations.csv`. Это данные социальной/VK Flash-игры, а не каталог Castaways.\n\n## Основные цифры\n\n- Записей в исходном items.json: **{len(raw)}**.\n- После удаления только полностью идентичных повторов: **{len(unique)}** записей с уникальными ID.\n- Уникальных типов: **{len(by_type)}**.\n- Построек: **{category_counts.get('building',0)}**.\n- Посевных культур: **{category_counts.get('seed',0)}**.\n- Рецептов: **{category_counts.get('recipe',0)}**.\n- Обычных локаций: **{category_counts.get('location',0)}**.\n- Исследовательских локаций: **{category_counts.get('explorationLocation',0)}**.\n\n## Файлы\n\n- `items_unique.json` — все записи после удаления только точных дублей; вложенные поля сохранены.\n- `items_index.csv` — общий плоский индекс всех записей, сложные поля оставлены JSON-строками.\n- `buildings.csv`, `seeds.csv`, `recipes.csv`, `decorations.csv`, `wood_trees.csv`, `fruit_trees.csv`, `stones.csv`, `piers.csv`, `path_parts.csv` — отдельные каталоги.\n- `recipes_resolved.csv` — рецепты с попыткой разрешить ID ингредиентов и результата в названия.\n- `locations_original.csv`, `exploration_locations.csv`, `locations_manifest_audit.csv` — карты и сведения о локациях.\n- `asset_reference_audit.csv` — сверка ссылок на изображения из items.json с оригинальным манифестом.\n- `relations_unresolved_grouped.csv` — сгруппированные ссылки из item_relations.csv, которые не разрешились автоматически. Они могут быть динамическими символами/группами, а не повреждёнными записями.\n- `key_building_facts.csv` — отдельная подборка ключевых зданий и их механик.\n- `type_summary.csv`, `catalog_summary.json` — статистика.\n\n## Про Excel 2019\n\nВсе CSV используют разделитель `;` и UTF-8 с BOM, чтобы Excel 2019 открывал кириллицу и столбцы корректно.\n\n## Важные оговорки\n\n`assets.csv` — это манифест оригинального клиента: он сообщает относительный путь, SHA-1 и размер ресурса. Он **не содержит сами байты изображений и SWF**. Поэтому `FOUND` в `asset_reference_audit.csv` означает, что файл указан в оригинальном манифесте, но для извлечения самого изображения нужен соответствующий SWF/ResPack-файл.\n\nCastaways не считается полным источником. Отсутствие объекта или растения в APK Castaways не является доказательством его отсутствия в социальной игре. Все неизвестные объекты следует сохранять со статусом «не знакомо игроку, дата появления неизвестна».\n'''
    (out/'README_RU.md').write_text(readme,encoding='utf-8')

    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(f'Created outputs in {out.resolve()}')

if __name__=='__main__': main()

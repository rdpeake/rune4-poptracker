"""Rebuild the Forge / Crafting / Cooking grid maps and the pins that sit on them.

The three `images/maps/grid_*.png` are not artwork: each is a sheet of the item
tiles from `images/items/`, and `locations/_Crafting.json` puts one pin in the
marker band above every tile. Image and pins are laid out by the same pass, so
they must be regenerated together or the pins slide off the tiles.

Tiles are grouped by the recipe sheet's Subtype -- the same grouping the item
panel's tabs use, so a weapon sits with its own kind on both -- and sorted by
name inside each group, case-insensitively. That reproduces the shipped maps
exactly, so an item upstream adds or renames lands in its group without
disturbing anything else. A subtype the group order does not name sorts last.

Rendering is `tools/gen_grid_maps.mjs` (node + @napi-rs/canvas); this only builds
its input and writes the pins back. Verified byte-identical against the shipped
maps before the Gloves split.

    npm install @napi-rs/canvas && python3 tools/export_grid_maps.py
"""
import collections
import copy
import csv
import json
import os
import subprocess
import tempfile

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
MAPS = ('Forge', 'Crafting', 'Cooking')
# recovered from the shipped maps: the order the subtypes run in on each sheet
GROUPS = {
    'Forge':    ('Short Sword', 'Long Sword', 'Dual Blade', 'Spear',
                 'Axe/Hammer', 'Fist', 'Staff', 'Farm Tool'),
    'Crafting': ('Armor', 'Shield', 'Headgear', 'Shoes', 'Accessories'),
    'Cooking':  ('Knife', 'Frying Pan', 'Pot', 'Oven', 'Steamer', 'Mixer',
                 'Handmade'),
}


def subtypes():
    """item name -> recipe Subtype, keyed the way parse_csv keys it (last wins)"""
    out = {}
    with open(PACK + 'stub/rf4/data/Rune Factory 4 AP - Recipes.csv',
              newline='', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            n = (row.get('Name') or '').strip()
            if n:
                out[n] = (row.get('Subtype') or '').strip()
    return out


def sections_by_map():
    """map name -> {item name: the section path a pin must ref}

    Cooking draws one sheet but its sections live under three nodes -- Cooking,
    Cooking/EZ and Cooking/Pro -- so the path cannot be assumed from the map.
    """
    out = collections.defaultdict(dict)
    for m in MAPS:
        fname = 'Cooking' if m == 'Cooking' else m
        doc = json.load(open(PACK + 'locations/%s.json' % fname, encoding='utf-8'))
        root = doc[0] if isinstance(doc, list) else doc

        def walk(n, path):
            p = path + [n.get('name', '')]
            for s in (n.get('sections') or []):
                if s.get('name'):
                    out[m][s['name']] = '/'.join(x for x in p if x) + '/' + s['name']
            for c in (n.get('children') or []):
                walk(c, p)
        walk(root, [])
    return out


def main():
    sub = subtypes()

    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    img_of = {i['name']: i['img'] for i in items}

    secs = sections_by_map()
    cats = {'Crafting': []}
    for m in MAPS:
        rank = {g: i for i, g in enumerate(GROUPS[m])}
        names = sorted(secs[m],
                       key=lambda n: (rank.get(sub.get(n), len(rank)), n.lower()))
        for n in names:
            if n not in img_of:
                raise SystemExit('no item image for %r' % n)
            cats['Crafting'].append({'path': secs[m][n], 'name': n, 'img': img_of[n],
                                     'map': m})
        print('%-9s %4d tiles' % (m, len(names)))

    with tempfile.TemporaryDirectory() as tmp:
        # the renderer groups by the first path segment, which is the map for all
        # three sheets, and filters on the map recorded alongside each tile
        payload = {'Crafting': [dict(c) for c in cats['Crafting']]}
        json.dump(payload, open(tmp + '/cats.json', 'w'))
        subprocess.run(['node', PACK + 'tools/gen_grid_maps.mjs',
                        tmp + '/cats.json', PACK + 'images/maps'], check=True)
        split = json.load(open(PACK + 'images/maps/grid_split.json', encoding='utf-8'))
        os.remove(PACK + 'images/maps/grid_split.json')

    p = PACK + 'locations/_Crafting.json'
    raw = open(p, encoding='utf-8').read()
    doc = json.loads(raw)
    root = doc[0] if isinstance(doc, list) else doc
    tmpl = copy.deepcopy(root['children'][0])
    kids = []
    for grid in split:
        for pin in grid['pins']:
            node = copy.deepcopy(tmpl)
            node['name'] = pin['path'].replace('/', ' › ')
            node['sections'] = [{'ref': pin['path']}]
            ml = copy.deepcopy(node['map_locations'][0])
            ml['map'], ml['x'], ml['y'] = grid['mapName'], pin['x'], pin['y']
            node['map_locations'] = [ml]
            kids.append(node)
    root['children'] = kids
    open(p, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(doc, indent=4, ensure_ascii=False) + ('\n' if raw.endswith('\n') else ''))
    print('pins written %4d' % len(kids))


if __name__ == '__main__':
    main()

"""Rebuild every grid map and the pins that sit on them.

`images/maps/grid_*.png` are not artwork: each is a sheet of the item tiles from
`images/items/`, and `locations/_Crafting.json` / `locations/_Shipments.json` put
one pin in the marker band above every tile. Image and pins come out of the same
pass, so they must be regenerated together or the pins slide off the tiles.

Layout is taken from the pins already on disk -- their order, their grouping into
labelled bands, and which sheet they belong to. That keeps a rebuild to exactly
what changed (the tiles themselves) instead of reshuffling a sheet every time.
Run it after anything that touches images/items/.

The tame sheets work the same way but draw `images/monsters/` instead, so run it
after anything that touches either directory.

    npm install --prefix tools @napi-rs/canvas && python3 tools/export_grid_maps.py
"""
import collections
import copy
import json
import os
import re
import subprocess
import sys
import tempfile

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
SOURCES = ('locations/_Crafting.json', 'locations/_Shipments.json')
TAMES = ('locations/_Tames.json',)


def sheets(sources):
    """map name -> the pins on it, in order, as (section path, source file)"""
    out = collections.OrderedDict()
    for src in sources:
        doc = json.load(open(PACK + src, encoding='utf-8'))
        root = doc[0] if isinstance(doc, list) else doc
        for node in (root.get('children') or []):
            for ml in (node.get('map_locations') or []):
                ref = (node.get('sections') or [{}])[0].get('ref')
                if ref:
                    out.setdefault(ml['map'], []).append((ref, src))
    return out


def slug(s):
    return re.sub(r'[^a-z0-9()+]', '', s.lower())


def item_art():
    """section name -> tile, for the crafting and shipment sheets"""
    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    by_name = {i['name']: i['img'] for i in items}
    # a section keeps the AP location's wording, which can differ from the item's
    # display name (the apworld ships one item literally called "progression"),
    # so fall back to the pack code, which never changes
    by_code = {i['codes']: i['img'] for i in items}
    by_slug = {slug(i['codes']): i['img'] for i in items}

    def art(name):
        if name.startswith('Boss - '):      # boss drops are prefixed on the pin
            name = name[len('Boss - '):]
        return by_name.get(name) or by_code.get(name) or by_slug.get(slug(name))
    return art


def monster_art():
    """section name -> tile, for the tame sheets"""
    have = set(os.listdir(PACK + 'images/monsters'))

    def art(name):
        f = slug(name) + '.png'             # the Boss prefix is part of the name here
        return 'images/monsters/' + f if f in have else None
    return art


def collect(sources, art, prefix):
    """the gen_grid_maps.mjs input for one family of sheets"""
    maps, owner = [], {}
    for mapname, pins in sheets(sources).items():
        entries = []
        for ref, src in pins:
            name = ref.rsplit('/', 1)[-1]
            entries.append({'path': ref, 'name': name,
                            'group': ref.split('/')[0], 'img': art(name)})
            owner[ref] = src
        missing = [e['name'] for e in entries if not e['img']]
        if missing:
            raise SystemExit('no %s image for %s' % (prefix or 'item', missing[:4]))
        fileslug = mapname.lower().replace(' ', '')
        maps.append({'mapName': mapname, 'file': 'grid_%s.png' % fileslug,
                     'items': entries})
        print('%-26s %4d tiles' % (mapname, len(entries)))
    return maps


def main():
    maps = (collect(SOURCES, item_art(), 'item')
            + collect(TAMES, monster_art(), 'monster'))

    # the shipped file names predate this tool, so keep them
    KNOWN = {'Forge': 'grid_forge.png', 'Crafting': 'grid_crafting.png',
             'Cooking': 'grid_cooking.png',
             'Shipments Selphia': 'grid_shipments_selphia.png',
             'Shipments Selphia Plains': 'grid_shipments_selphiaplains.png',
             'Shipments Autumn Road': 'grid_shipments_autumnroad.png',
             'Shipments Sercerezo Hill': 'grid_shipments_sercerezohill.png',
             'Shipments Anywhere': 'grid_shipments_anywhere.png',
             'Tames Selphia': 'grid_tames_selphia.png',
             'Tames Selphia Plains': 'grid_tames_selphiaplains.png',
             'Tames Autumn Road': 'grid_tames_autumnroad.png',
             'Tames Sercerezo Hill': 'grid_tames_sercerezohill.png',
             'Tames Anywhere': 'grid_tames_anywhere.png'}
    for m in maps:
        m['file'] = KNOWN.get(m['mapName'], m['file'])

    with tempfile.TemporaryDirectory() as tmp:
        json.dump(maps, open(tmp + '/maps.json', 'w'))
        subprocess.run(['node', PACK + 'tools/gen_grid_maps.mjs',
                        tmp + '/maps.json', PACK + 'images/maps', PACK], check=True)
    split = json.load(open(PACK + 'images/maps/grid_split.json', encoding='utf-8'))
    os.remove(PACK + 'images/maps/grid_split.json')

    # The pins are tied to marker positions, so a rerun must not move them.
    # Feeding the existing order back in should reproduce them exactly -- check
    # that it did, and refuse rather than write unless a move is the point.
    placed = {}
    for grid in split:
        for pin in grid['pins']:
            placed[pin['path']] = (grid['mapName'], pin['x'], pin['y'])
    moved, checked, docs = [], 0, {}
    for src in SOURCES + TAMES:
        docs[src] = json.load(open(PACK + src, encoding='utf-8'))
        root = docs[src][0] if isinstance(docs[src], list) else docs[src]
        for node in (root.get('children') or []):
            ref = (node.get('sections') or [{}])[0].get('ref')
            if ref not in placed or not node.get('map_locations'):
                continue
            checked += 1
            ml = node['map_locations'][0]
            want = placed[ref]
            if (ml['map'], ml['x'], ml['y']) != want:
                moved.append((ref, (ml['map'], ml['x'], ml['y']), want))
                ml['map'], ml['x'], ml['y'] = want
    if moved and '--relayout' not in sys.argv:
        raise SystemExit('%d pins would move, e.g. %s -- images written but pins '
                         'left alone. Rerun with --relayout if that is the point.'
                         % (len(moved), moved[:3]))
    if moved:
        for src, doc in docs.items():
            with open(PACK + src, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(json.dumps(doc, indent=4, ensure_ascii=False) + '\n')
        print('%d pins moved with their tiles' % len(moved))
    else:
        print('%d pins checked, every one still in place' % checked)


if __name__ == '__main__':
    main()

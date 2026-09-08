"""Rebuild every grid map and the pins that sit on them.

`images/maps/grid_*.png` are not artwork: each is a sheet of the item tiles from
`images/items/`, and `locations/_Crafting.json` / `locations/_Shipments.json` put
one pin in the marker band above every tile. Image and pins come out of the same
pass, so they must be regenerated together or the pins slide off the tiles.

Layout is `generated/grid_layout.json`: which sheet a pin belongs on, its band,
its place in the order and the ruler under it. Run it after anything that
touches images/items/.

The tame sheets work the same way but draw `images/monsters/` instead, so run it
after anything that touches either directory. A tame tile also carries a strip
of every item that tames it, drawn under the face from `images/chips/` -- bare
icons rather than the `images/items/` cards, because at the size four of them
fit, a card is mostly frame. `generated/tame_gifts.json` says which, in the
game's own order.

A crafted tile carries the same strip, saying what the recipe is made of. Its
slots come from the game's own tables (`generated/recipes.json`), not from the
Recipes CSV, because a slot is often a CLASS of item -- any Strings, any
Minerals -- where the CSV names one example. A class chip is the icon the game
itself puts on that class. Quantities are folded into the chip's own count, so
four Yarn is one chip, and the pin's name spells the whole list out.

    npm install --prefix tools @napi-rs/canvas && python3 tools/export_grid_maps.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
SOURCES = ('locations/_Crafting.json', 'locations/_Shipments.json')
TAMES = ('locations/_Tames.json',)
TAME_PREFIX = 'Tames '
# 24 columns is what the widest shipment band needs; a tame sheet wrapped that
# late came out half again as wide as the pane it is shown in
TAME_COLS = 16
GIFTS = 'tools/generated/tame_gifts.json'
RECIPES = 'tools/generated/recipes.json'
CHIPS = 'images/chips/'


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


def chip_of():
    """item or class name -> its bare chip, cut from the game's own icon"""
    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    code = {i['name']: i['codes'] for i in items
            if i.get('name') and i.get('codes')}
    have = set(os.listdir(PACK + CHIPS))

    def chip(name, is_class=False):
        f = ('class_' + slug(name) if is_class else code.get(name) or '') + '.png'
        if f not in have:
            raise SystemExit('no chip for %s -- run '
                             'tools/gamedata/export_chips.py' % name)
        return CHIPS + f
    return chip


def gift_art():
    """pin -> the bare chips for every item that tames the monster"""
    gifts = json.load(open(PACK + GIFTS, encoding='utf-8'))
    chip = chip_of()

    def art(ref):
        name = ref.rsplit('/', 1)[-1]
        if name.startswith('Boss - '):
            name = name[len('Boss - '):]
        return [chip(g['item']) for g in gifts.get(name, {}).get('gifts', [])]
    return art


def recipe_art(paths):
    """pin -> the bare chips for what the recipe is made of

    Only the crafted sheets get them: a shipment can share a recipe's name --
    a Recovery Potion is both -- and badging the shipment tile would change the
    row pitch on a sheet that has no ingredients to show.
    """
    rec = json.load(open(PACK + RECIPES, encoding='utf-8'))['recipes']
    chip = chip_of()

    def art(ref):
        if ref not in paths:
            return []
        e = rec.get(ref.rsplit('/', 1)[-1])
        return [chip(s['name'], s['class']) for s in e['needs']] if e else []
    return art


def pins_of(src):
    """the refs one location file puts on a grid"""
    doc = json.load(open(PACK + src, encoding='utf-8'))
    root = doc[0] if isinstance(doc, list) else doc
    return {r for n in (root.get('children') or [])
            for r in [(n.get('sections') or [{}])[0].get('ref')] if r}


def monster_art():
    """section name -> tile, for the tame sheets"""
    have = set(os.listdir(PACK + 'images/monsters'))

    def art(name):
        f = slug(name) + '.png'             # the Boss prefix is part of the name here
        return 'images/monsters/' + f if f in have else None
    return art


def collect(plan, art, prefix, cols=None, chips=None, fit=False):
    """the gen_grid_maps.mjs input for one family of sheets

    Sheet, bands and order all come from the plan -- generated/grid_layout.json
    -- so a rebuild reshuffles a sheet only when the plan says to.
    """
    maps = []
    for mapname, pins in plan.items():
        entries = []
        for pin in pins:
            ref = pin['path']
            name = ref.rsplit('/', 1)[-1]
            entries.append({'path': ref, 'name': name, 'group': pin['band'],
                            'sub': pin['sub'], 'img': art(name),
                            'glyphs': chips(ref) if chips else []})
        missing = [e['name'] for e in entries if not e['img']]
        if missing:
            raise SystemExit('no %s image for %s' % (prefix, missing[:4]))
        fileslug = re.sub(r'[^a-z0-9]+', '_', mapname.lower()).strip('_')
        entry = {'mapName': mapname, 'file': 'grid_%s.png' % fileslug,
                 'items': entries}
        if cols:
            entry['cols'] = cols
        if fit:
            entry['fit'] = True
        maps.append(entry)
        print('%-26s %4d tiles' % (mapname, len(entries)))
    return maps


def main():
    plan = json.load(open(PACK + 'tools/generated/grid_layout.json',
                          encoding='utf-8'))
    tame = {k: v for k, v in plan.items() if k.startswith(TAME_PREFIX)}
    item = {k: v for k, v in plan.items() if not k.startswith(TAME_PREFIX)}
    # The crafted sheets pick their own width. They are the ones that grew a
    # chip strip, and a sheet is scaled to fit a pane far wider than it is
    # tall, so the columns that suit the shipment sheets leave them half size.
    # The shipment sheets keep the 24 they were laid out with.
    crafted = pins_of('locations/_Crafting.json')
    craft = {k: v for k, v in item.items() if v[0]['path'] in crafted}
    ship = {k: v for k, v in item.items() if k not in craft}
    items = item_art()          # the whole items.json index; built once
    maps = (collect(ship, items, 'item')
            + collect(craft, items, 'item',
                      chips=recipe_art(crafted), fit=True)
            + collect(tame, monster_art(), 'monster',
                      cols=TAME_COLS, chips=gift_art()))

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

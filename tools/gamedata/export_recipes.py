"""Take every recipe's ingredient slots out of the game's own tables.

`Recipes.csv` has an `Ingredients` column, and for 231 of the 584 recipes the
pack badges it is wrong the same way the Tame CSV's `Friend Item` was wrong:
where the game asks for a CLASS of item it names one example instead. The
game's Red Ribbon is `Red Grass + Cloths and Skins + Strings`; the CSV says
`Red Grass + Insect Carapace + Old Bandage`, which in a randomiser reads as a
hunt for one bandage when any string will do. Curry Bread is worse -- the CSV
expands the `Curry` slot into a whole curry recipe.

So the slots come from the game. `rf3Recipe*.bin` is 22 tables, one per
crafting utensil, each `NLCL` + a 24-byte preamble + 20-byte records:

    uint16 @0   count, in the first record; unused after
    uint16 @4   the item the recipe makes
    uint16 @6   six ingredient slots, zero-terminated
    uint16 @18  the record's own index

A slot holds either an item id or one of the 19 CLASS pseudo-items the game
keeps at ids 1083-1101 -- Minerals, Liquids, Claws and Fangs, Sticks and Stems,
Cloths and Skins, Furs, Strings, Shards, Powders and Spores, Scales, Shells and
Bones, Stones, Turnip, Crystals, Jewels, Feathers, Jam, Curry, Squid. Those are
`I_Catecory00..18` in the bundle, in that order, so a class has its own icon.

The layout was confirmed against the CSV rather than assumed: with class slots
taken as wildcards, 601 of the 611 recipes agree with it slot for slot and in
order. The ten that do not are the Curry three (the CSV expands the class), the
two Snapper names below, and five alternate recipes the CSV does not carry.

A repeated slot is a quantity -- Hand-Knit Scarf is four Yarn -- so repeats are
folded into a count. A result with more than one record has genuine alternates:
Recovery Potion is `Medicinal Herb + Green Grass` OR one `Blue Grass`. The
first record is the recipe; the rest are kept as alternates.

    python3 tools/gamedata/export_recipes.py

Needs `_input/bundleMain.mbundle`. Writes tools/generated/recipes.json, which
IS committed, so everything downstream runs without the game files.
"""
import collections
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from extract_map_graph import MBundle                      # noqa: E402
from paths import BUNDLE, PACK, need                       # noqa: E402

OUT = PACK + 'tools/generated/recipes.json'
NAMES = 'rf3TxtItem_split2_1.eng'
CLASS0, CLASS_N = 1083, 19          # the class pseudo-items, = I_Catecory00..18
HEAD, REC = 24, 20                  # preamble, record size

# The apworld renamed two fish and lost the game's typographic quotes; the six
# items the game calls plain "Mushroom" it numbered instead.
ALIAS = {
    'Grape ”Liqueur”': 'Grape Liqueur',
    'Lover Snapper': 'Throbby Snapper',
    'Psn. Rainbow Trout': 'Rainbow Trout',
}
MUSHROOM = range(48, 54)            # ids 48-53, all named "Mushroom"
# the game gives the weapon and the accessory the same name; the table it is in
# says which, and the apworld's suffix says the same thing
BY_TABLE = {('Gloves', 'Acce'): 'Gloves (Accessory)',
            ('Gloves', 'WeaponN'): 'Gloves (Weapon)'}


def item_names(b, idx):
    """the game's 1108 item names, in item-id order"""
    d = b.read(idx[NAMES])
    pairs, off, first = [], 8, None
    while True:
        ln, o = struct.unpack_from('<ii', d, off)
        if first is None:
            first = o
        if off + 8 > first:
            break
        pairs.append((ln, o))
        off += 8
    return [d[o:o + ln].split(b'\0')[0].decode('utf-8', 'replace')
            for ln, o in pairs]


def tables(b, idx):
    """utensil -> [(result id, [slot ids])], in the game's own order"""
    out = {}
    for fn in sorted(n for n in idx if n.startswith('rf3Recipe')):
        d = b.read(idx[fn])
        n = (len(d) - HEAD) // REC
        rows = []
        for i in range(1, n):
            r = struct.unpack_from('<10H', d, HEAD + i * REC)
            if not r[2]:                # a placeholder row, result "(nothing)"
                continue
            rows.append((r[2], [v for v in r[3:9] if v]))
        out[re.sub(r'^rf3Recipe|\.bin$', '', fn)] = rows
    return out


def main():
    b = MBundle(need(BUNDLE))
    idx = {n: i for i, n in enumerate(b.names())}
    names = item_names(b, idx)
    classes = names[CLASS0:CLASS0 + CLASS_N]

    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    known = {i['name'] for i in items if i.get('name')}

    def item(i):
        nm = names[i]
        if i in MUSHROOM:
            return 'Mushroom %d' % (i - MUSHROOM.start + 1)
        return ALIAS.get(nm, nm)

    doc, unknown = {}, set()
    for utensil, rows in sorted(tables(b, idx).items()):
        for result, slots in rows:
            made = BY_TABLE.get((names[result], utensil)) or item(result)
            need_ = []
            for s in slots:
                if CLASS0 <= s < CLASS0 + CLASS_N:
                    nm, is_class = classes[s - CLASS0], True
                else:
                    nm, is_class = item(s), False
                    if nm not in known:
                        unknown.add(nm)
                if need_ and need_[-1]['name'] == nm:
                    need_[-1]['count'] += 1     # a repeat is a quantity
                    continue
                need_.append({'name': nm, 'count': 1, 'class': is_class})
            e = doc.setdefault(made, {'utensil': utensil, 'needs': need_,
                                      'alt': []})
            if e['needs'] is not need_:
                e['alt'].append(need_)
    if unknown:
        raise SystemExit('%d ingredients name no pack item, e.g. %s -- add an '
                         'ALIAS' % (len(unknown), sorted(unknown)[:6]))
    doc = {'classes': classes,
           'recipes': {k: doc[k] for k in sorted(doc)}}
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    n = doc['recipes']
    print('wrote %s: %d recipes, %d with an alternate, %d with a class slot'
          % (os.path.relpath(OUT, PACK), len(n),
             sum(1 for v in n.values() if v['alt']),
             sum(1 for v in n.values() if any(s['class'] for s in v['needs']))))


if __name__ == '__main__':
    main()

"""Cut the badge chips a grid tile carries, as bare icons with no tile behind.

`images/items/` is a 64px rounded CARD per item -- a coloured background, a rim
and the icon centred on white. That card is most of the picture, which is fine
when an item is the whole tile and wasteful when four of them have to fit around
a monster's face: at the size four cards can be drawn, you see four white boxes.

The game's own icons are RGBA with real alpha, so cutting them without the card
gives a chip that is all subject and no frame. It can then be drawn small, tight
against its neighbours and over the tile's edge without boxing it in.

Two things want chips, and they want the same ones often enough to share a
directory: the items that tame a monster (`generated/tame_gifts.json`) and the
ingredients a recipe asks for (`generated/recipes.json`). Item chips are keyed
by the pack's item code, so `images/chips/<code>.png` sits beside
`images/items/<code>.png` and means the same item.

A recipe slot can also ask for a CLASS of item rather than a named one -- any
Minerals, any Strings. The game draws those with `I_Catecory00..18`, one per
class in the order `generated/recipes.json` lists them, and they are cut to
`images/chips/class_<slug>.png`.

    python3 tools/gamedata/export_chips.py

Needs the game icons: run `extract_textures.py` first. The output IS committed,
so the tools that draw the sheets keep working from committed data alone.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# paths also pins SOURCE_DATE_EPOCH, so ImageMagick leaves the tIME chunk out
from paths import CONVERT, PACK, ICONS, need               # noqa: E402

OUT = PACK + 'images/chips/'
SIZE = 48                          # drawn at 11-18px; 48 leaves room to scale


def cut(src, dst):
    subprocess.run([CONVERT, src, '-trim', '+repage',
                    '-resize', '%dx%d' % (SIZE, SIZE),
                    '-background', 'none', '-gravity', 'center',
                    '-extent', '%dx%d' % (SIZE, SIZE), dst],
                   stderr=subprocess.DEVNULL)


def main():
    icons = need(ICONS)
    gifts = json.load(open(PACK + 'tools/generated/tame_gifts.json',
                           encoding='utf-8'))
    recipes = json.load(open(PACK + 'tools/generated/recipes.json',
                             encoding='utf-8'))
    plan = json.load(open(PACK + 'tools/item_icons.json', encoding='utf-8'))
    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    code_of = {i['name']: i['codes'] for i in items
               if i.get('name') and i.get('codes')}

    want = {g['item'] for v in gifts.values() for g in v['gifts']}
    for v in recipes['recipes'].values():
        for slots in [v['needs']] + v['alt']:
            want |= {s['name'] for s in slots if not s['class']}

    os.makedirs(OUT, exist_ok=True)
    made, missing = 0, []
    for name in sorted(want):
        code = code_of.get(name)
        stem = plan['items'].get(code) if code else None
        src = icons + (stem or '') + '.png'
        if not (stem and os.path.exists(src)):
            missing.append(name)
            continue
        cut(src, OUT + code + '.png')
        made += 1
    if missing:
        raise SystemExit('no game icon for %d chips: %s'
                         % (len(missing), missing[:6]))

    for i, name in enumerate(recipes['classes']):
        src = '%sI_Catecory%02d.png' % (icons, i)
        cut(need(src), OUT + 'class_' + re.sub(r'[^a-z0-9]', '', name.lower())
            + '.png')
        made += 1
    print('wrote %d chips to %s' % (made, os.path.relpath(OUT, PACK)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

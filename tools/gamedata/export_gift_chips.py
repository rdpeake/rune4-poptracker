"""Cut the tame gifts as bare icons, with no tile behind them.

`images/items/` is a 64px rounded CARD per item -- a coloured background, a rim
and the icon centred on white. That card is most of the picture, which is fine
when an item is the whole tile and wasteful when four of them have to fit around
a monster's face: at the size four cards can be drawn, you see four white boxes.

The game's own icons are RGBA with real alpha, so cutting them without the card
gives a chip that is all subject and no frame. It can then be drawn small, tight
against its neighbours and over the monster tile's edge without boxing it in.

Only the items that are actually a tame gift are cut -- 143 of the game's 1250
icons -- keyed by the pack's item code so `images/gifts/<code>.png` sits beside
`images/items/<code>.png` and means the same item.

    python3 tools/gamedata/export_gift_chips.py

Needs the game icons: run `extract_textures.py` first. The output IS committed,
so the tools that draw the sheets keep working from committed data alone.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import PACK, ICONS, need                        # noqa: E402

# ImageMagick stamps a tIME chunk into every PNG it writes, so an identical
# rebuild produces different bytes. SOURCE_DATE_EPOCH makes it leave it out.
os.environ.setdefault('SOURCE_DATE_EPOCH', '0')

CONVERT = '/usr/bin/convert-im6.q16'
OUT = PACK + 'images/gifts/'
SIZE = 48                          # drawn at 11-18px; 48 leaves room to scale


def main():
    icons = need(ICONS)
    gifts = json.load(open(PACK + 'tools/generated/tame_gifts.json',
                           encoding='utf-8'))
    plan = json.load(open(PACK + 'tools/item_icons.json', encoding='utf-8'))
    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    code_of = {i['name']: i['codes'] for i in items
               if i.get('name') and i.get('codes')}

    want = sorted({g['item'] for v in gifts.values() for g in v['gifts']})
    os.makedirs(OUT, exist_ok=True)
    made, missing = 0, []
    for name in want:
        code = code_of.get(name)
        stem = plan['items'].get(code) if code else None
        src = icons + (stem or '') + '.png'
        if not (stem and os.path.exists(src)):
            missing.append(name)
            continue
        subprocess.run([CONVERT, src, '-trim', '+repage',
                        '-resize', '%dx%d' % (SIZE, SIZE),
                        '-background', 'none', '-gravity', 'center',
                        '-extent', '%dx%d' % (SIZE, SIZE),
                        OUT + code + '.png'], stderr=subprocess.DEVNULL)
        made += 1
    if missing:
        raise SystemExit('no game icon for %d gifts: %s' % (len(missing), missing[:6]))
    print('wrote %d gift chips to %s' % (made, os.path.relpath(OUT, PACK)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

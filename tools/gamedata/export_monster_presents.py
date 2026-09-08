"""Export what each monster likes to be given, out of the game's own tables.

The apworld's Tame CSV carries one `Friend Item` per monster. The game carries
up to four, with a value on each, and the CSV keeps one of them -- the
highest-valued in 33 of the 40 monsters whose values differ, but the lowest in
the other 7, so upstream's pick is a judgement call rather than a rule. A
randomiser can hand you the four in any order or not at all, so the pack wants
all of them.

Three tables in bundleMain.mbundle, all of them indexed rather than searched:

    rf3MonsterPresent.bin       209 records of 4 x (item id u32, value u32),
                                indexed by MONSTER ID - 48, so ids 48..256
    rf3TxtNpc_split2_1.eng      monster id -> species name
    rf3TxtItem_split2_1.eng     item id    -> item name

The -48 was found from a histogram of (record index - monster id) over the 149
gifts the apworld already knew: it is the only offset that puts every one of
them inside its own monster's record, with no misses.

It is a PRESENT table, not a drop or produce table, though it looks like one for
a wolf: of its 143 distinct items about 90 are cooked dishes, grown crops, mined
minerals, potions and tools -- a Gobble Box does not produce Disastrous Dish.
The overlap that remains is real rather than coincidence, since a tamed wolf
does drop the Fur it likes. Note `Fur` (a drop) and `Fur (S/M/L)` (barn produce)
are different items and only the first is ever listed.

The value is how much the monster wants that gift -- 4, 5 (the default), 8, 10,
15 -- on the same scale the villager tables use for presents, where they also
run negative. Nothing in the monster table is negative, so monsters have likes
and no dislikes. It is NOT the friendship rung at which a barn animal upgrades
its produce, even though Buffamoo's Milk (S)/(M)/(L) at 5/8/10 reads like one:
Wooly, which produces Fur (S) through (L), lists neither, and no boss carries a
value other than 5.

A monster with no items is one that cannot be tamed -- Sano, Uno, Ancient Bone,
Rafflesia, Ventuswill and the rest of the Floating Empire cast are all empty.
14 species names cover two ids each (a boss instance and a tameable one, as with
Ambrosia); the populated record wins.

    python3 tools/gamedata/export_monster_presents.py

Writes tools/generated/tame_gifts.json, which IS committed, so the tools that
draw the tame sheets need the plan and not the game files.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                               # noqa: E402
from extract_map_graph import MBundle                      # noqa: E402

OUT = paths.PACK + 'tools/generated/tame_gifts.json'
# the apworld annotates one boss with its role; the game just names the monster
ALIAS = {'Emerald (Boss)': 'Emerald'}
# four items the game and the apworld spell differently. The pack's tiles are
# keyed by the apworld's name, so emit that -- and every other name is checked
# against items/items.json below, so a fifth one fails here rather than
# silently losing a badge.
ITEM_ALIAS = {
    'Gold Doom Pumpkin': 'Gldn. Doom Pumpkin',
    'Grt. Autumn Grass': 'Big Autumn Grass',
    'King Gold Cabbage': 'Golden King Cabbage',
    'Ultra Moondrop': 'Ultra Moondrop Flower',
}
FIRST_ID = 48                     # record 0 is monster id 48
SLOTS = 4


def strings(bundle, names, entry):
    """a TEXT table: magic, count, then count x (length, offset)"""
    d = bundle.read(names.index(entry))
    if d[:4] != b'TEXT':
        raise SystemExit('%s is not a TEXT table' % entry)
    n = struct.unpack_from('<I', d, 4)[0]
    out = []
    for i in range(n):
        ln, off = struct.unpack_from('<II', d, 8 + i * 8)
        out.append(d[off:off + ln].decode('cp932', 'replace').strip())
    return out


def main():
    b = MBundle(paths.need(paths.BUNDLE, 'from a Rune Factory 4 Special install'))
    names = b.names()
    item = strings(b, names, 'rf3TxtItem_split2_1.eng')
    npc = strings(b, names, 'rf3TxtNpc_split2_1.eng')

    raw = b.read(names.index('rf3MonsterPresent.bin'))
    words = struct.unpack('<%dI' % (len(raw) // 4), raw)
    stride = SLOTS * 2
    recs = [words[i:i + stride] for i in range(0, len(words), stride)]

    doc = {}
    for k, r in enumerate(recs):
        mid = k + FIRST_ID
        name = npc[mid] if mid < len(npc) else ''
        # a slot may carry a value with no item; that is padding, not a gift
        gifts = [{'item': ITEM_ALIAS.get(item[r[i]], item[r[i]]),
                  'value': r[i + 1]}
                 for i in range(0, stride, 2) if r[i]]
        if not name or not gifts:
            continue                                       # untameable
        # keep the game's own slot order. Ranking by value reads as "best
        # first" and is exactly wrong for a randomiser: it puts Milk (L) ahead
        # of Milk (S) for Buffamoo, and the (L) is the one you cannot get yet.
        # The slot order already runs easiest-first where it matters -- Apple
        # before Baked Apple, a Goblin's drops before its Onigiri.
        # the same name can cover a boss instance and a tameable one; whichever
        # record actually holds gifts is the one that answers
        if name in doc and doc[name]['gifts'] != gifts:
            raise SystemExit('%s: two ids disagree on the gifts' % name)
        doc[name] = {'id': mid, 'gifts': gifts}

    known = json.load(open(paths.PACK + 'items/items.json', encoding='utf-8'))
    known = known if isinstance(known, list) else known['items']
    known = {i['name'] for i in known if i.get('name')}
    unknown = sorted({g['item'] for v in doc.values() for g in v['gifts']} - known)
    if unknown:
        raise SystemExit('the pack has no item called %s -- add it to ITEM_ALIAS'
                         % unknown[:4])

    for said, real in ALIAS.items():
        if real in doc and said not in doc:
            doc[said] = doc[real]

    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write('\n')
    n = sum(len(v['gifts']) for v in doc.values())
    print('wrote %s' % os.path.relpath(OUT, paths.PACK))
    print('  %d monsters that can be tamed, %d gifts, %d untameable'
          % (len(doc), n, len(recs) - len(doc)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

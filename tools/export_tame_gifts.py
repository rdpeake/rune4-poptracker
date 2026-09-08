"""Name each tame's grid pin with the gift that tames it.

A tame tile badges the gifts in its corner, which says which items they are only
if you already know the icons. The names are free: `MapTooltip` prints a
`ref` section's OWN name when it has one and falls back to the target's only
when it does not (`maptooltip.cpp:112`), and the line was pure duplication --
the tooltip's header already reads `Floating Empire > Tame > Blood Panther` and
the section under it said `Blood Panther` again. So it now reads
`Blood Panther - gifts: Panther Claw, Fur, Quality Fur, Devil Blood`, and
nothing new is drawn until you point at a tile.

Every gift is listed, not the one the apworld picked. A randomiser can hand you
the four in any order or none of them, so which ones are open to you is the
question the pin has to answer -- and 114 of the pack's 149 tames have more than
one. They are in the game's own order of preference, best first.

The name goes on the REF in `locations/_Tames.json`, never on the canonical
section in the region file: a section's full id is its parent plus its name
(`locationsection.cpp` `getFullID`), so that name IS the ref path every pin uses
and the path `location_mapping.lua` keys the AP id to. Renaming it there would
break both.

Gifts come from `generated/tame_gifts.json` (`gamedata/export_monster_presents.py`,
out of the game's own tables), so this runs from committed data and needs
neither the apworld nor the game files.

    python3 tools/export_tame_gifts.py
"""
import json
import os
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
GIFTS = PACK + 'tools/generated/tame_gifts.json'
SRC = 'locations/_Tames.json'


def main():
    gifts = json.load(open(GIFTS, encoding='utf-8'))

    doc = json.load(open(PACK + SRC, encoding='utf-8'))
    root = doc[0] if isinstance(doc, list) else doc
    named, missing, changed = 0, [], 0
    for node in (root.get('children') or []):
        for sec in (node.get('sections') or []):
            ref = sec.get('ref')
            if not ref:
                continue
            name = ref.rsplit('/', 1)[-1]
            key = name[len('Boss - '):] if name.startswith('Boss - ') else name
            if key not in gifts:
                missing.append(ref)
                continue
            got = [g['item'] for g in gifts[key]['gifts']]
            want = '%s - gift%s: %s' % (name, '' if len(got) == 1 else 's',
                                        ', '.join(got))
            changed += sec.get('name') != want
            sec['name'] = want
            named += 1
    if missing:
        raise SystemExit('no gift for %d pins, e.g. %s'
                         % (len(missing), missing[:3]))

    with open(PACK + SRC, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, indent=4, ensure_ascii=False) + '\n')
    print('%d tame pins named, %d changed' % (named, changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Check every chest pin against the room the game actually puts the chest in.

Three sources say where a chest is, and only the first is the game's own:

    generated/map_objects.json   the MOBJ object the game places, by field flag
    the apworld's Chests.csv     a hand-entered Region + Room Code
    locations/*.json             where the pack draws the pin

The chest sheet addresses a save byte and mask; export_map_objects turns that
into the field flag the game file carries, so a chest joins to a map id outright
rather than through its name. The pin is then read back and matched to the
nearest room the pack draws, which is how move_pins placed it.

    A  the sheet and the game agree and the pin is somewhere else -- a pack bug
    B  the sheet disagrees with the game; the pin follows the sheet
    C  the game puts the chest in a room the pack draws no map for

It also reports ids whose room and item have drifted from the sheet, and chests
the map files place that the apworld does not list at all.

Usage:  python3 tools/verify/check_chest_rooms.py [-v]
Non-zero exit if anything is in A.
"""
import collections
import csv
import glob
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, PACK + 'tools/apworld')
sys.path.insert(0, PACK + 'tools/gamedata')
import load                                         # noqa: E402
from export_map_objects import CHEST, flag_of, rooms_by_flag  # noqa: E402

SHEET = 'Rune Factory 4 AP - Chests'


def pin_of_node():
    """{node path: [(map, x, y)]} -- a node can be pinned in several rooms."""
    out = {}
    for path in sorted(glob.glob(PACK + 'locations/*.json')):
        def walk(nodes, above):
            for nd in nodes:
                here = above + [nd.get('name', '')]
                if nd.get('map_locations'):
                    out['/'.join(here)] = [(m['map'], m['x'], m['y'])
                                           for m in nd['map_locations']]
                walk(nd.get('children') or [], here)
        walk(json.load(open(path, encoding='utf-8')), [])
    return out


def ap_paths():
    """{ap id: node path} and {ap id: section name}, from location_mapping."""
    text = open(PACK + 'scripts/autotracking/location_mapping.lua',
                encoding='utf-8').read()
    full = {int(i): p.lstrip('@').split('/')
            for i, p in re.findall(r'\[(\d+)\]\s*=\s*\{"([^"]+)"', text)}
    return ({i: '/'.join(p[:-1]) for i, p in full.items()},
            {i: p[-1] for i, p in full.items()})


def main():
    rooms = json.load(open(PACK + 'tools/generated/room_pins.json',
                           encoding='utf-8'))
    on_map = collections.defaultdict(list)
    for map_id, r in rooms.items():
        on_map[r['map']].append((r['x'], r['y'], map_id, r['label']))

    flags = rooms_by_flag(lambda o: o['type'] == CHEST)
    pins = pin_of_node()
    paths, apid_section = ap_paths()
    load.apworld()                                  # puts rf4 on the path
    # decoded out of the apworld and parsed once; the checks below walk it
    # three times over, and DictReader is a one-shot iterator besides
    sheet = list(csv.DictReader(io.StringIO(load.csv_text(SHEET))))

    found = collections.defaultdict(list)
    ok = 0
    for row in sheet:
        game = sorted(flags[flag_of(row['Byte'], row['Mask'])])
        labels = ['%s %s' % (rooms[g]['map'], rooms[g]['label'])
                  for g in game if g in rooms]
        said = row['Room Code'].strip()
        node = paths.get(int(row['APID'], 16))
        spots = pins.get(node) if node else None
        if not spots:
            found['A'].append((row['Location Name'], said, labels, 'no pin'))
            continue
        at, at_label = None, []
        for pin in spots:
            near = sorted((math.hypot(pin[1] - x, pin[2] - y), map_id, label)
                          for x, y, map_id, label in on_map[pin[0]])
            _, one, one_label = near[0]
            at_label.append('%s %s' % (pin[0], one_label))
            if one in game:
                at = one
        at_label = ' + '.join(at_label)
        if at is not None:
            ok += 1
        elif not labels:
            found['C'].append((row['Location Name'], said, labels, at_label))
        elif any(l.endswith(' ' + said) for l in labels):
            found['A'].append((row['Location Name'], said, labels, at_label))
        else:
            found['B'].append((row['Location Name'], said, labels, at_label))

    total = ok + sum(len(v) for v in found.values())
    print('%d chests: %d pinned on the room the game puts them in' % (total, ok))
    titles = {'A': 'sheet and game agree on the room; this id opens another',
              'B': 'the sheet disagrees with the game; the pin follows the sheet',
              'C': 'the game puts it in a room the pack draws no map for'}
    for key in 'ABC':
        if not found[key]:
            continue
        print('\n%s. %s  (%d)' % (key, titles[key], len(found[key])))
        for name, said, labels, at in sorted(found[key]):
            print('     %s\n         sheet %-5s | game %-28s | pin %s'
                  % (name, said, ' + '.join(labels) or '-', at))
    crossed, agrees = [], []
    for row in sheet:
        path = paths.get(int(row['APID'], 16))
        if path is None:
            crossed.append((row['APID'], row['Room Code'], row['Items'], None))
            continue
        node, section = path.split('/')[-1], apid_section[int(row['APID'], 16)]
        if section.strip() != row['Items'].strip():
            crossed.append((row['APID'], row['Room Code'], row['Items'],
                            '%s / %s' % (node, section)))
        elif node.strip() != row['Room Code'].strip():
            # The pack naming a different room than the sheet is only wrong if
            # the game does not back it: Yokmir Cave's chest is E2, not F2.
            game = ['%s' % rooms[g]['label']
                    for g in flags[flag_of(row['Byte'], row['Mask'])]
                    if g in rooms]
            if node.strip() not in game:
                crossed.append((row['APID'], row['Room Code'], row['Items'],
                                '%s / %s' % (node, section)))
            else:
                agrees.append((row['APID'], row['Room Code'], node))
    print('\n%d of %d chest ids carry the sheet\'s own room and item'
          % (total - len(crossed) - len(agrees), total))
    for apid, said, node in agrees:
        print('     %s  sheet says %-5s the pack and the game both say %s'
              % (apid, said, node))
    for apid, said, item, got in crossed:
        print('     %s  sheet %-5s %s' % (apid, said, item))
        print('              pack  %s' % got)
    unlisted = sorted(set(flags) - {flag_of(r['Byte'], r['Mask'])
                                    for r in sheet})
    print('\n%d chests in the map files, %d of them listed by the apworld'
          % (len(flags), len(flags) - len(unlisted)))
    for flag in unlisted:
        for room in sorted(flags[flag]):
            r = rooms.get(room)
            print('     flag %-4d byte %03x mask %02x  %-14s %s'
                  % (flag, 0x200 + flag // 8, 1 << (flag % 8), room,
                     '%s %s' % (r['map'], r['label']) if r else '(no pack map)'))
    return 1 if found['A'] or crossed else 0


if __name__ == '__main__':
    sys.exit(main())

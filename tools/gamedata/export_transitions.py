"""Where one pack map is entered from another, out of the game's own map files.

An `.rf4m` carries one MAPJ chunk per doorway (see `extract_map_graph.py` for
the container and the field layout). Word 5 is the room you arrive in and words
1,2 are the trigger volume you have to stand in to go there. A doorway whose two
ends are drawn on different pack maps is a map transition -- which is exactly
what the area pins point at, and what was being guessed at before.

Writes `tools/generated/transitions.json`:

    source map -> destination map -> [room label, ...]

the labels being the rooms on the SOURCE map you leave from, named the way the
maps print them. A link with more than one label has more than one door.

    python3 tools/gamedata/export_transitions.py            report
    python3 tools/gamedata/export_transitions.py --write    write it
"""
import collections
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import BUNDLE, PACK, need                  # noqa: E402
sys.path.insert(0, PACK + 'tools')

from extract_map_graph import MBundle, chunks         # noqa: E402
from room_ids import room_names                       # noqa: E402

SEASON = re.compile(r'_(SUMMER|AUTUMN|WINTER)$')
OUT = PACK + 'tools/generated/transitions.json'


def links():
    """(source map, destination map) -> the source room labels you leave from"""
    rooms = room_names()
    pins = json.load(open(PACK + 'tools/generated/room_pins.json',
                          encoding='utf-8'))
    b = MBundle(need(BUNDLE, 'from a Rune Factory 4 Special install'))
    names = b.names()
    at = {n: i for i, n in enumerate(names)}

    out = collections.defaultdict(set)
    for fn in sorted(n for n in names if n.endswith('.rf4m')):
        src = SEASON.sub('', fn[:-5])
        if src not in pins:
            continue                       # a room the pack draws no map for
        blob = b.read(at[fn])
        for tag, off, size in chunks(blob):
            if tag != 'MAPJ' or size < 36:
                continue
            dst = SEASON.sub('', rooms.get(
                struct.unpack_from('<I', blob, off + 20)[0], ''))
            if dst not in pins or pins[dst]['map'] == pins[src]['map']:
                continue
            out[(pins[src]['map'], pins[dst]['map'])].add(pins[src]['label'])
    return out


def main():
    found = links()
    doors = collections.defaultdict(dict)
    for (a, b), labels in found.items():
        doors[a][b] = sorted(labels)
    doors = {a: dict(sorted(v.items())) for a, v in sorted(doors.items())}

    if '--write' in sys.argv:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(doors, fh, indent=1, sort_keys=True)
            fh.write('\n')
        print('wrote %s' % os.path.relpath(OUT, PACK))
    else:
        for a, v in doors.items():
            for b, labels in v.items():
                print('  %-24s -> %-24s %s' % (a, b, ', '.join(labels)))
        print('(--write to save)')
    print('%d links over %d maps, %d doors'
          % (sum(len(v) for v in doors.values()), len(doors),
             sum(len(l) for v in doors.values() for l in v.values())))


if __name__ == '__main__':
    main()

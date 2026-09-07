"""Extract the objects the game places in each room into generated/map_objects.json.

Every MAP_*.rf4m carries one MOBJ chunk per placed object, 64 bytes of 16 int32:

    0      object type -- 44 chest, 47 barrier, 53 box, and ~90 others
    6      scale, Q12
    13     field flag, or -1 for an object the save file does not track
    14,15  x, y within the room

The field flag is the same index the apworld's barrier_flags.json and
box_flags.json carry, and it is what the Chests/Shipments sheets address as a
byte and a mask:

    flag = (byte - 0x200) * 8 + log2(mask)        byte is hex in the sheet

That was confirmed three ways: MAP_DUNG_A01's barrier is flag 596, which is byte
0x24a bit 4, the byte chest_locs.csv gives for a chest sharing it; and Water
Ruins C2 and C1 (bytes 0x213/0x214, masks 0x80/0x02) are flags 159 and 161,
which are the type-44 objects in MAP_DUNG_B09 and B11. All 181 chests in the
sheet resolve to a type-44 object this way, and to nothing else.

Usage:  python3 tools/gamedata/export_map_objects.py [--all] [path to bundle]
--all keeps the unflagged objects too, which nothing in the pack reads.
The game files are not part of the pack; point it at a copy or a Steam install.
"""
import collections
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import BUNDLE, PACK                      # noqa: E402
sys.path.insert(0, PACK + 'tools')
from extract_map_graph import MBundle, chunks       # noqa: E402

NO_FLAG = 0xFFFFFFFF
CHEST, BARRIER, BOX, SEARCH = 44, 47, 53, 35

# The only four types whose identity is established rather than guessed. Each is
# confirmed against a table the apworld ships: every one of the 181 rows in
# Chests.csv resolves to a type 44 and to nothing else, box_flags.json's flags
# are all type 53, barrier_flags.json declares obj_type 47, which its flags hit
# 229 times, and search_flags.json declares 35, which all 28 of its flags hit.
# About ninety other types appear and are left unnamed.
KIND = {CHEST: 'chest', BARRIER: 'barrier', BOX: 'box', SEARCH: 'search'}


def flag_of(byte, mask):
    """The sheets' hex byte and mask as one field-flag index."""
    return (int(byte, 16) - 0x200) * 8 + int(mask, 16).bit_length() - 1


SEASON = re.compile(r'_(SUMMER|AUTUMN|WINTER)$')
PLACED = 'tools/generated/map_objects.json'


def rooms_by_flag(match=lambda o: 'kind' in o):
    """{field flag: {map id}} for the placed objects `match` accepts.

    Reads what main() wrote rather than the bundle, so the tools that only have
    the pack agree with the ones that have the game. A room's seasonal copies
    carry the same objects, so the suffix is dropped and they collapse onto the
    one id the rest of the tools use.
    """
    out = collections.defaultdict(set)
    placed = json.load(open(PACK + PLACED, encoding='utf-8'))
    for room, objs in placed.items():
        for o in objs:
            if o['flag'] >= 0 and match(o):
                out[o['flag']].add(SEASON.sub('', room))
    return out


def read(path=None, flagged_only=True):
    """{room name: [{type, flag, x, y}]} for the objects the save file tracks.

    Only flagged objects are kept by default, and committed: they are the chests,
    barriers and boxes a check can be, and the unflagged rest -- scenery, spawn
    points, gathering nodes -- is 6952 of 8329 records nothing here reads.
    """
    b = MBundle(path or BUNDLE)
    names = b.names()
    idx = {n: i for i, n in enumerate(names)}
    out = collections.OrderedDict()
    for fn in sorted(n for n in names if n.endswith('.rf4m')):
        d = b.read(idx[fn])
        objs = []
        for tag, off, size in chunks(d):
            if tag != 'MOBJ' or size < 64:
                continue
            w = struct.unpack_from('<16i', d, off)
            if flagged_only and w[13] < 0:
                continue
            obj = {'type': w[0], 'flag': w[13], 'x': w[14], 'y': w[15]}
            if w[0] in KIND:
                obj['kind'] = KIND[w[0]]
            objs.append(obj)
        if objs:
            out[fn[:-5]] = objs
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else BUNDLE
    if not os.path.exists(path):
        raise SystemExit('no such archive: %s\n'
                         'Pass the path to Bundle/bundleMain.mbundle.' % path)
    objs = read(path, flagged_only='--all' not in sys.argv)
    out = PACK + PLACED
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(objs, f, indent=1, sort_keys=False)
        f.write('\n')
    kinds = collections.Counter(o.get('kind') for v in objs.values() for o in v)
    print('%d rooms, %d objects -> %s' %
          (len(objs), sum(len(v) for v in objs.values()),
           os.path.relpath(out, PACK)))
    print('  chest %d  barrier %d  box %d  search %d  unidentified %d in %d types'
          % (kinds['chest'], kinds['barrier'], kinds['box'], kinds['search'],
             kinds[None],
             len({o['type'] for v in objs.values() for o in v
                  if 'kind' not in o})))


if __name__ == '__main__':
    main()

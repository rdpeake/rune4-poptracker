"""Say which room the game puts every chest, barrier, box and search check in.

The map files place each of them as an object carrying a field flag, and the
apworld addresses that same flag: the flag tables carry it
on the entry, and the Chests sheet as a hex byte and a mask (see
gamedata/export_map_objects.py). So a check joins to a map id through the game's
own data rather than through the room code in its name.

Written out to generated/check_rooms.json so the pin placement can use it
without a copy of the apworld. A check can name more than one map id: the
Obsidian Mansion chest sits in Selphia, which the game draws four seasonal
copies of, and they collapse to one room here.

Usage:  python3 tools/apworld/export_check_rooms.py [--write]
"""
import collections
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, HERE)
sys.path.insert(0, PACK + 'tools/gamedata')
import load                                          # noqa: E402
from export_map_objects import flag_of, rooms_by_flag  # noqa: E402

SHEET = 'Rune Factory 4 AP - Chests'

OUT = PACK + 'tools/generated/check_rooms.json'


def main():
    ap = load.apworld()
    where = rooms_by_flag()
    out = {}

    def put(apid, flags):
        rooms = sorted({r for f in flags for r in where.get(f, ())})
        if rooms:
            out[str(apid)] = rooms

    # the Chests sheet is keyed by APID and has no Name column, so it is read
    # straight rather than through load.csv_rows
    for row in csv.DictReader(io.StringIO(load.csv_text(SHEET))):
        put(int(row['APID'], 16), [flag_of(row['Byte'], row['Mask'])])

    # The box table reuses "<Region> Barrier - RmN" names, so its entries
    # collide in location_data_table; go through the flag tables, which carry
    # the id and the flag on the entry, and keep only ids that are locations.
    L = ap.Locations
    kinds = load.map_kinds(ap)
    real = {d.address for d in L.location_data_table.values()
            if d.loc_type in kinds and d.address is not None}
    flags = collections.defaultdict(list)
    for table in (L.barrier_data_table, L.box_data_table,
                  getattr(L, 'search_data_table', {})):
        for entry in table.values():
            if entry.apid in real:
                flags[entry.apid].append(entry.field_flag)
    for apid, f in flags.items():
        put(apid, f)

    if '--write' in sys.argv:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, indent=1, sort_keys=True)
            f.write('\n')
    print('%d checks placed by the game\'s own objects%s'
          % (len(out), '' if '--write' in sys.argv else '  (--write to save)'))
    many = {k: v for k, v in out.items() if len(v) > 1}
    print('  %d name more than one room' % len(many))


if __name__ == '__main__':
    main()

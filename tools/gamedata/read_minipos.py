"""Decode rf3MapMiniPos.bin -- where every room sits on its area's minimap.

The game's own answer to "which rooms are on this map, and where". Room ids
come from `room_ids`; the 873 records cover every real map, the two ids above
that being resources rather than maps.

    NLCL header, 28 bytes: magic, tag, 0, 0, 1, <size>, <count=873>
    then 873 records of 13 dwords, indexed by MAP ID directly:

        0      sheet        which minimap picture. Texture = archive resource
                            12199 + sheet, so 0 is mini_map_00_city, 4 is
                            01_dung_a, 31 is 30_farm, 61 is 60_m_room. 73, or
                            anything above 87, draws the blank 99_dummy.
        1,2    origin x,y   where the map's world origin (tile 0,0) sits on the
                            sheet; player and NPC markers hang off this.
        3,4    reveal x,y   top-left of the fog-of-war box uncovered once the
                            map has been visited -- a hand-placed box around the
                            map's art, NOT a copy of the origin.
        5,6    reveal w,h   its size. Zero means no fog: towns, interiors.
        7,8    scale x,y    Q12 fixed point, half-texture pixels per sub-unit
        9      icon slot    counter for fanning out NPC icons in one building
        10     parent sheet where this map's NPCs show when the player is
                            elsewhere on that sheet; 73 means none.
        11,12  icon x,y     where those icons appear on the parent sheet

The sheet is a 256-space in half-texture pixels over the 512px texture, so a
room's drawn area is the reveal box and its centre in texture pixels is

    (2*reveal_x + reveal_w, 2*reveal_y + reveal_h)

Use the reveal box and not the origin: they differ on most maps, and only the
box sizes a room that spans several cells.

    python3 tools/gamedata/read_minipos.py                  rooms per minimap texture
    python3 tools/gamedata/read_minipos.py <texture name>   the rooms on one minimap
"""
import os
import re
import struct
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import ART, MINIPOS, PACK, need          # noqa: E402
sys.path.insert(0, PACK + 'tools')
from room_ids import room_names                     # noqa: E402
HEADER_BYTES, RECORD_BYTES, RECORD_COUNT = 28, 52, 873
SEASON = re.compile(r'_(SUMMER|AUTUMN|WINTER)$')


def sheets():
    """{map id: minimap texture} for every room the game really draws.

    Unlike `read`, a room with no fog-of-war box is kept: towns and interiors
    have none, but they still name the sheet they belong to, which is what says
    which of the pack's maps a room is on.

    A record whose origin and scale are both zero was never filled in, and its
    sheet field is a zero that happens to mean the first texture -- Selphia's.
    Yokmir Forest A09 to A13, Water Ruins B18 and B19 and Obsidian Mansion C20
    and C21 are all like that, and all of them are doorless, textureless stubs
    sitting alongside MAP_DUMMY_* and MAP_NULL in the map files. They are
    dropped rather than read as being in town. A seasonal variant is usually
    blank in the same way and inherits from the room it is a variant of.
    """
    blob = open(need(MINIPOS), 'rb').read()
    names = sorted(f[:-4] for f in os.listdir(need(ART)))
    rooms = room_names()

    def record(map_id):
        return struct.unpack_from(
            '<13i', blob, HEADER_BYTES + RECORD_BYTES * map_id)

    def sheet_of(map_id):
        """the minimap this record names, or None where it names none"""
        r = record(map_id)
        if r[0] != 73 and r[0] < len(names) and any(r[i] for i in (1, 2, 7, 8)):
            return names[r[0]]
        return None

    # A room's seasonal copies are drawn on the same sheet, so a copy that does
    # carry a record stands in for the ones that do not. That needs every real
    # record first, hence the two passes.
    filled = {}
    for map_id, name in rooms.items():
        if map_id < RECORD_COUNT and sheet_of(map_id):
            filled.setdefault(SEASON.sub('', name), sheet_of(map_id))

    out = {}
    for map_id, name in rooms.items():
        if map_id >= RECORD_COUNT:
            continue
        sheet = sheet_of(map_id) or filled.get(SEASON.sub('', name))
        if sheet:
            out[map_id] = sheet
    return out


def read():
    """{minimap texture name: [(map name, cx, cy, w, h), ...]}

    cx/cy are room centres and w/h its size, all in texture pixels, taken from
    the fog-of-war reveal box.
    """
    blob = open(need(MINIPOS), 'rb').read()
    sheets = sorted(f[:-4] for f in os.listdir(need(ART)))
    names = room_names()
    out = {}
    for map_id in sorted(names):
        if map_id >= RECORD_COUNT:
            continue
        record = struct.unpack_from(
            '<13i', blob, HEADER_BYTES + RECORD_BYTES * map_id)
        sheet, x, y, w, h = record[0], record[3], record[4], record[5], record[6]
        # sheet 73 and anything past the table is the blank; no fog box at
        # all means the map is not drawn on a minimap
        if sheet == 73 or sheet >= len(sheets) or not (w or h):
            continue
        out.setdefault(sheets[sheet], []).append(
            (names[map_id], 2 * x + w, 2 * y + h, 2 * w, 2 * h))
    return out


def main():
    got = read()
    if len(sys.argv) > 1:
        rooms = got.get(sys.argv[1], [])
        for n, x, y, w, h in sorted(rooms, key=lambda r: (r[2], r[1])):
            print('  %-28s (%3d,%3d)  %3dx%-3d' % (n, x, y, w, h))
        print('%d rooms' % len(rooms))
        return
    for sheet in sorted(got):
        print('%-28s %3d rooms' % (sheet, len(got[sheet])))
    print('\n%d minimaps, %d rooms' % (len(got), sum(len(v) for v in got.values())))


if __name__ == '__main__':
    main()

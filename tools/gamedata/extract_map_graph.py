"""Extract the game's own room adjacency graph into tools/generated/map_graph.json.

The retail game ships every room as MAP_*.rf4m inside Bundle/bundleMain.mbundle.
That archive is a binary-plist variant; the reader below is a port of
darkxex's Rune-Factory-4-Special-Mbundle-Extractor, which unpacks the archive
and nothing more -- everything about what is inside a room file is worked out
here. It seeks rather than loading, so a 4.7 GB archive costs nothing to query.

An .rf4m is chunked: 4CC tag + uint32 size + payload. Eight tags appear:

    MOBJ   64 bytes    map objects -- the barriers and boxes the apworld's
                       field_flags name
    PALD  512
    MAPJ   36          the doorways, below
    MTXN    4          texture reference
    MSEA    4          season
    MGRP    4          group
    MLIG   12          lighting
    ATTR  10-16 KB     the per-room attribute block, one per room

MAPJ ("map jump") is nine uint32 and describes one doorway end to end:

    0      destination MAP, or 0xFFFFFFFF for a jump inside this area
    1,2    the trigger volume's x, y -- where you have to stand
    3,4    its w, h; 32x32 is much the commonest
    5      destination ROOM        <- the only field the graph uses
    6,7    where you arrive, x and y
    8      which way you face: 0, 90, 180, 270 and a few odd angles

Field 5 was identified statistically rather than guessed: across a 250-room
sample its values land in the source room's own dungeon 89% of the time against
an 8% baseline, and every other field scores at baseline.

WHAT IS NOT HERE. A link that only opens once some condition is met is not in
MAPJ -- there is no flag or condition field, every one of the nine words is
accounted for above -- and it is not in any other chunk either: no chunk of any
MAP_DUNG_C room so much as mentions rooms 322 or 323, which sit on Selphia's
minimap and which nothing in the map files reaches. Neither do the seasonal
variants differ; MAP_CITY_05, _06 and _07 have byte-identical MAPJ across all
four seasons, so the only room files that vary are seasonal and they vary in
scenery, not exits. Whatever gates a conditional link lives outside the room
files, most likely in emdeb.bin -- 137 KB, magic "EMDb", an offset table, and
the one public attempt at reading it is marked "do not use" by its author.

So this graph is the unconditional doorways of one world state. That is enough
to walk a dungeon and no more, and it must not be read as "everywhere you can
get to".

Usage:  python3 tools/gamedata/extract_map_graph.py [path to bundleMain.mbundle]
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
from paths import BUNDLE, PACK, need                # noqa: E402
sys.path.insert(0, PACK + 'tools')
from room_ids import room_names                     # noqa: E402

DEFAULT = BUNDLE
SEASON = re.compile(r'_(SUMMER|AUTUMN|WINTER)$')


class MBundle:
    """Read-only view of a .mbundle; seeks, never loads the whole archive."""

    def __init__(self, path):
        self.f = open(path, 'rb')
        self.f.seek(0, 2)
        self.size = self.f.tell()
        self.f.seek(self.size - 16)
        self.top, self.table_off = struct.unpack('>qq', self.f.read(16))
        self.f.seek(self.top + 10)
        self.n = struct.unpack('>i', self.f.read(4))[0]
        self.refs = struct.unpack('>%di' % (self.n * 2), self.f.read(self.n * 8))
        self.f.seek(self.table_off)
        wide = struct.unpack('>i', self.f.read(4))[0] == 0
        self.f.seek(self.table_off)
        raw = self.f.read(self.size - 26 - self.table_off)
        w = 8 if wide else 4
        cnt = len(raw) // w
        self.offsets = struct.unpack('>%d%s' % (cnt, 'q' if wide else 'i'),
                                     raw[:cnt * w])

    def _blob(self, off):
        self.f.seek(off)
        ln = self.f.read(1)[0] & 0x0F
        if ln == 0x0F:
            self.f.read(1)
            ln = struct.unpack('>i', self.f.read(4))[0]
        return self.f.read(ln)

    def names(self):
        out = []
        self.f.seek(8)
        for _ in range(self.n):
            ln = self.f.read(1)[0] & 0x0F
            if ln == 0x0F:
                self.f.read(1)
                ln = struct.unpack('>i', self.f.read(4))[0]
            out.append(self.f.read(ln).decode('cp932', 'replace'))
        return out

    def read(self, index):
        return self._blob(self.offsets[self.refs[self.n + index]])


def chunks(d):
    """MAPD's payload is a flat stream of 4CC + uint32 size + bytes."""
    out, off = [], 8
    while off + 8 <= len(d):
        tag = d[off:off + 4].decode('latin1', 'replace')
        size = struct.unpack_from('<I', d, off + 4)[0]
        if size > len(d):
            break
        out.append((tag, off + 8, size))
        off += 8 + size
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        raise SystemExit('no such archive: %s\n'
                         'Pass the path to Bundle/bundleMain.mbundle.' % path)
    rooms = room_names()

    b = MBundle(path)
    names = b.names()
    idx = {n: i for i, n in enumerate(names)}
    walk = collections.defaultdict(set)
    warp = collections.defaultdict(set)
    for fn in sorted(n for n in names if n.endswith('.rf4m')):
        src = SEASON.sub('', fn[:-5])
        d = b.read(idx[fn])
        for tag, off, size in chunks(d):
            if tag != 'MAPJ' or size < 24:
                continue
            room = struct.unpack_from('<I', d, off + 20)[0]
            if room in rooms:
                dst = SEASON.sub('', rooms[room])
                if dst != src:
                    walk[src].add(dst)
            area = struct.unpack_from('<I', d, off)[0]
            if area != 0xFFFFFFFF and area in rooms:
                warp[src].add(SEASON.sub('', rooms[area]))

    out = PACK + 'tools/generated/map_graph.json'
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'walk': {k: sorted(v) for k, v in sorted(walk.items())},
                   'warp': {k: sorted(v) for k, v in sorted(warp.items())}},
                  f, indent=1, sort_keys=True)
    print('wrote %s' % out)
    print('  rooms with exits %5d' % len(walk))
    print('  walk edges       %5d' % sum(len(v) for v in walk.values()))
    print('  warp edges       %5d' % sum(len(v) for v in warp.values()))


if __name__ == '__main__':
    main()

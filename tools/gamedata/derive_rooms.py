"""Work out where every room sits, from the game's own map data.

    rf3MapMiniPos.bin  a room's fog-of-war box on its minimap  (read_minipos)
    tools/rooms.json   what the pack calls that room, whether to draw it, and
                       where in the box the label sits
    generated/map_layout.json  where each texture is drawn on its pack image

One pass over those produces every derived room file, so changing a label in
`rooms.json` needs this tool and nothing else:

    tools/generated/room_positions.json   map -> label -> x,y     labels on the maps
    tools/generated/room_extents.json     map -> label -> w,h     how big the room is
    tools/generated/room_pins.json        map id -> where its pin goes
    tools/generated/room_shown.json       map -> the labels the maps draw

All three are generated. Edit `rooms.json` or `map_art.json`, never these.

    python3 tools/gamedata/derive_rooms.py            report what would change
    python3 tools/gamedata/derive_rooms.py --write    write them

An anchor puts the label somewhere other than the middle of the room, which is
how a label ends up legitimately off the road: a stairway is drawn outside the
room it belongs to, and Obsidian Mansion's corridors are one room wide so their
labels are written beside them.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from paths import PACK                              # noqa: E402
from read_minipos import read                       # noqa: E402
from map_art import solid_box                       # noqa: E402

INSET = 12          # how far inside the box an anchored label sits, in px


def anchored(cx, cy, w, h, anchor):
    """the label's point: the box centre, or in towards a named edge"""
    if not anchor:
        return cx, cy
    dx = max(0.0, w / 2 - INSET)
    dy = max(0.0, h / 2 - INSET)
    if 'w' in anchor:
        cx -= dx
    if 'e' in anchor:
        cx += dx
    if 'n' in anchor:
        cy -= dy
    if 's' in anchor:
        cy += dy
    return cx, cy


def derive():
    """[{map_id, label, map, x, y, w, h, show}, ...], one per room drawn.

    The one table the rest of the pipeline projects out of: labels and their
    positions for the maps, extents for laying pins out inside a room, and the
    map id a barrier or box names.

    A room can be drawn on more than one pack map -- the Overworld composites
    Selphia Plains, Autumn Road and Sercerezo Hill -- so every placement is
    kept, in draw order, and `pins` picks between them.
    """
    on_sheet = read()
    rooms = json.load(open(PACK + 'tools/rooms.json'))
    art = json.load(open(os.environ.get(
        'MAP_LAYOUT', PACK + 'tools/generated/map_layout.json')))
    maps = {m['img'].replace('images/maps/', ''): m['name']
            for m in json.load(open(PACK + 'maps/maps.json'))}
    out = []
    for img, cfg in art.items():
        name = maps.get(img)
        if not name:
            continue
        for piece in cfg['art']:
            tex = piece['tex']
            if tex not in on_sheet:
                tex = re.sub(r'_\d+$', '', tex)
            # the texture's own art box, against which the piece was placed
            art_w, art_h, art_x, art_y = solid_box(piece['tex'])
            scale_x, scale_y = piece['w'] / art_w, piece['h'] / art_h
            for map_id, cx, cy, box_w, box_h in on_sheet.get(tex, []):
                room = rooms.get(map_id)
                if not room:
                    continue
                w, h = box_w * scale_x, box_h * scale_y
                x, y = anchored(piece['x'] + (cx - art_x) * scale_x,
                                piece['y'] + (cy - art_y) * scale_y,
                                w, h, room.get('anchor'))
                out.append({'map_id': map_id, 'label': room['label'],
                            'map': name, 'x': round(x), 'y': round(y),
                            'w': round(w), 'h': round(h),
                            'show': room.get('show') is not False})
    return out


def positions(derived):
    """{map: {label: [x, y]}}"""
    out = {}
    for r in derived:
        out.setdefault(r['map'], {})[r['label']] = [r['x'], r['y']]
    return out


def extents(derived):
    """{map: {label: [w, h]}}"""
    out = {}
    for r in derived:
        out.setdefault(r['map'], {})[r['label']] = [r['w'], r['h']]
    return out


def shown(derived):
    """{map: {labels the pack draws}} -- a room the pack knows only by its map
    number still needs a position, checks sit in it, but is not labelled."""
    out = {}
    for r in derived:
        if r['show']:
            out.setdefault(r['map'], set()).add(r['label'])
    return out


def pins(derived):
    """{map id: {label, map, x, y}} -- what a barrier or box pin is placed on.

    Keyed by map id because that is how the apworld's flag tables name a room
    ("MAP_DUNG_A01.rf4m"), so no room-number-to-label matching is needed.

    Where a room is drawn twice, the pin goes on whichever map draws it larger:
    a map of its own always beats its corner of a composite.
    """
    best = {}
    for r in derived:
        seen = best.get(r['map_id'])
        if seen is None or r['w'] * r['h'] > seen['w'] * seen['h']:
            best[r['map_id']] = r
    return {map_id: {k: r[k] for k in ('label', 'map', 'x', 'y')}
            for map_id, r in best.items()}


def main():
    derived = derive()
    pos, ext = positions(derived), extents(derived)
    old = json.load(open(PACK + 'tools/generated/room_positions.json'))
    moved, added, gone = [], [], []
    for name in sorted(set(old) | set(pos)):
        o, n = old.get(name, {}), pos.get(name, {})
        for c in sorted(set(o) | set(n)):
            if c not in n:
                gone.append((name, c))
            elif c not in o:
                added.append((name, c))
            elif o[c] != n[c]:
                d = ((n[c][0]-o[c][0])**2 + (n[c][1]-o[c][1])**2) ** 0.5
                moved.append((round(d), name, c, tuple(o[c]), tuple(n[c])))
    moved.sort(reverse=True)
    print('%d labels across %d maps' % (sum(len(v) for v in pos.values()), len(pos)))
    print('  moved %d, added %d, dropped %d' % (len(moved), len(added), len(gone)))
    for d, nm, c, a, b in moved[:8]:
        print('    %-24s %-8s %-12s -> %-12s %3dpx' % (nm, c, a, b, d))
    if added:
        print('  added: %s' % ', '.join('%s/%s' % a for a in added[:8]))
    if gone:
        print('  dropped: %s' % ', '.join('%s/%s' % g for g in gone[:8]))
    if '--write' in sys.argv:
        drawn = {m: sorted(v) for m, v in sorted(shown(derived).items())}
        for path, data in (('tools/generated/room_positions.json', pos),
                           ('tools/generated/room_extents.json', ext),
                           ('tools/generated/room_pins.json', pins(derived)),
                           ('tools/generated/room_shown.json', drawn)):
            json.dump(data, open(PACK + path, 'w'), indent=1, sort_keys=True)
        print('\nwrote room_positions.json, room_extents.json, room_pins.json,'
              ' room_shown.json')


if __name__ == '__main__':
    main()

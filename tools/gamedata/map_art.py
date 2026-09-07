"""Where each map's art sits on its 670x600 canvas, and the texture geometry
the other map tools share.

Input is `tools/map_art.json`: per pack image, which mini_map_* texture(s) draw
it, how they are arranged where there is more than one, and the caption. Output
is `tools/generated/map_layout.json`, the rect each texture ends up occupying --
centred and as large as the frame allows. The two are separate files because
this writes one of them: a solver that overwrites its own input eventually eats
the hand-made part of it.

The art sits where it looks best and the room labels follow it, being placed
from the game's own table (see `derive_rooms.py`).

Also home to what the other map tools need: a texture's solid-art box. Its
alpha carries a wide glow, so a plain trim gives the box of the HALO, not the
map.

    python3 tools/gamedata/map_art.py            show the placements
    python3 tools/gamedata/map_art.py --write    write generated/map_layout.json
"""
import json
import os
import subprocess
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import ART as GM_ART, CONVERT, PACK, need  # noqa: E402

# the map area inside the frame's border, in 670x600 canvas coordinates
BOX = (12, 16, 646, 506)


def _dilate(m, w, h, n):
    for _ in range(n):
        o = bytearray(m)
        for y in range(h):
            r = y * w
            for x in range(w):
                if m[r + x]:
                    for dy in (-1, 0, 1):
                        yy = y + dy
                        if 0 <= yy < h:
                            rr = yy * w
                            for dx in (-1, 0, 1):
                                xx = x + dx
                                if 0 <= xx < w:
                                    o[rr + xx] = 1
        m = o
    return m


def bbox(m, w, h):
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        row = m[y * w:y * w + w]
        if 1 not in row:
            continue
        y0 = min(y0, y); y1 = y
        x0 = min(x0, row.index(1))
        x1 = max(x1, w - 1 - row[::-1].index(1))
    return x0, y0, x1, y1


_NET = {}


# Where a texture's alpha is the whole dungeon FOOTPRINT rather than its roads,
# fit to the cream path colour instead. Water Ruins needs it: its ground and
# lake are opaque, so alpha covers five times the actual road.
NETWORK_MIN = 0.30


def network(name):
    """the box of the texture's road network, in 512px coordinates

    Several textures carry a wide soft glow in the alpha, so a plain `-trim`
    gives the box of the HALO. The box returned here is the art proper; the
    renderer offsets the full texture, glow and all, to suit.
    """
    if name not in _NET:
        px = subprocess.run(
            [CONVERT, GM_ART + name + '.png', '-depth', '8', 'rgba:-'],
            capture_output=True).stdout
        count = len(px) // 4
        w = h = int(count ** 0.5)
        assert w * h == count, (name, count)

        def is_cream(i):
            r, g, b = px[4 * i], px[4 * i + 1], px[4 * i + 2]
            return r > 205 and g > 195 and r - b > 25

        mask = bytearray(count)
        cream = 0
        for i in range(count):
            if px[4 * i + 3] > 128:
                mask[i] = 1
                cream += is_cream(i)
        if cream and cream / sum(mask) < NETWORK_MIN:
            for i in range(count):
                if mask[i]:
                    mask[i] = 1 if is_cream(i) else 0
            mask = _dilate(mask, w, h, 2)          # close the outline back up
        x0, y0, x1, y1 = bbox(mask, w, h)
        _NET[name] = (x1 - x0 + 1, y1 - y0 + 1, x0, y0, w)
    return _NET[name]


def solid_box(name):
    """the box of the texture's art proper, in its own 512px coordinates"""
    return network(name)[:4]


def texture_size(name):
    """the full texture's edge in pixels, soft glow and all -- it is square"""
    return network(name)[4]


# ---------------------------------------------------------------- placement

def best_fit(margin=0.94):
    """Centre each map's art and scale it to fill the frame.

    A map drawn from several textures keeps their relative arrangement and is
    scaled as a group: Obsidian Mansion's two floors, Demon's Den's four rooms,
    the World Map's three fields, Sharance Maze's sixteen tiles. A group scales
    relative to the rects it is given, so the first pass over a hand-arranged
    one can shift a pixel as it rounds; it is stable after.
    """
    box_x, box_y, box_w, box_h = BOX
    art = {img: {'art': [dict(tex=p['tex'], x=p['x'], y=p['y'],
                              w=p['w'], h=p['h'])
                         for p in cfg['art']]}
           for img, cfg in json.load(open(PACK + 'tools/map_art.json')).items()}
    for cfg in art.values():
        pieces = cfg['art']
        if len(pieces) == 1:
            only = pieces[0]
            art_w, art_h, _, _ = solid_box(only['tex'])
            scale = min(box_w * margin / art_w, box_h * margin / art_h)
            only['w'], only['h'] = round(art_w * scale), round(art_h * scale)
            only['x'] = box_x + (box_w - only['w']) // 2
            only['y'] = box_y + (box_h - only['h']) // 2
        elif len(pieces) > 1:
            min_x = min(p['x'] for p in pieces)
            min_y = min(p['y'] for p in pieces)
            group_w = max(p['x'] + p['w'] for p in pieces) - min_x
            group_h = max(p['y'] + p['h'] for p in pieces) - min_y
            scale = min(box_w * margin / group_w, box_h * margin / group_h)
            left = box_x + (box_w - round(group_w * scale)) // 2
            top = box_y + (box_h - round(group_h * scale)) // 2
            for piece in pieces:
                piece['x'] = round(left + (piece['x'] - min_x) * scale)
                piece['y'] = round(top + (piece['y'] - min_y) * scale)
                piece['w'] = round(piece['w'] * scale)
                piece['h'] = round(piece['h'] * scale)
    return art


def main():
    art = best_fit()
    if '--write' in sys.argv:
        out = PACK + 'tools/generated/map_layout.json'
        with open(out, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(art, fh, indent=1, sort_keys=True)
            fh.write('\n')
        print('wrote tools/generated/map_layout.json')
    for img in sorted(art):
        for piece in art[img]['art']:
            print('  %-28s %-26s %4d,%-4d %4dx%d'
                  % (img[:-4], piece['tex'], piece['x'], piece['y'],
                     piece['w'], piece['h']))


if __name__ == '__main__':
    main()

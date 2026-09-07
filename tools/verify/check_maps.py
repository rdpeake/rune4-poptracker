"""Check the maps the tools make still match the ones the pack ships.

Two questions against two folders, both gitignored:

    _baseline/   the pack's own maps, copied in on each run. Re-rendering them
                 must come out byte-identical, or the art has drifted.
    _original/   the screen-capture maps the game art replaced, if you want the
                 stronger check. A pin that sat on drawn road there and does not
                 now is a REGRESSION; one that was already off it is not.

Only _baseline is automatic. Seed _original once, from the pack as it was
before the game art landed:

    git ls-tree --name-only main-with-art images/maps/ \\
      | while read f; do git show main-with-art:"$f" \\
          > tools/verify/_original/"${f#images/maps/}"; done

Without it the point check still runs, and reports anything off the art against
the list it recorded last time instead.

    python3 tools/verify/check_maps.py            snapshot, then compare
    python3 tools/verify/check_maps.py --skip-copy   keep the snapshot as it is
    python3 tools/verify/check_maps.py --yes      overwrite it without asking
    python3 tools/verify/check_maps.py --mark DIR ring the offending points

Replacing an existing snapshot asks first: it is the record of what the pack
looked like before, so overwriting it silently throws the comparison away.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
from collections import deque

# ImageMagick stamps a tIME chunk into every PNG it writes, so an
# identical rebuild produces different bytes and every icon shows as
# changed. SOURCE_DATE_EPOCH makes it leave the chunk out.
os.environ.setdefault('SOURCE_DATE_EPOCH', '0')

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, PACK + 'tools')
sys.path.insert(0, PACK + 'tools/gamedata')
from map_art import BOX, CONVERT, GM_ART, _dilate, bbox, solid_box  # noqa: E402

BASELINE = os.path.join(HERE, '_baseline') + '/'
ORIGINAL = os.path.join(HERE, '_original') + '/'
ACCEPTED = BASELINE + 'accepted_off_art.json'
MAPS_DIR = PACK + 'images/maps/'
TEMPLATE = 'Blank.png'      # the frame with no map on it, for _brown

PARKED_X = 34            # aggregate pins are stacked in this column, off-map

# Points that sit off the road and are meant to: a pin with no room to sit in,
# on an entrance icon or a bridge narrower than the word. An off-centre LABEL is
# an anchor in rooms.json instead. An entry is a room code, or a literal (x, y)
# for a pin with no code.
OFF_PATH = {
    'Selphia_plains.png': {'D5', 'F3'},
    'Sercerezo Hill.png': {(209, 294), (244, 341)},
}


def _raw(args, n):
    d = subprocess.run(args, capture_output=True).stdout
    assert len(d) == n, (len(d), n, args[1])
    return d


_TEMPLATE = None


def _brown(path):
    """pixels of the drawn map: the path outline's hue, and darker than the page"""
    x, y, w, h = BOX
    d = _raw([CONVERT, path, '-crop', '%dx%d+%d+%d' % (w, h, x, y), '+repage',
              '-depth', '8', 'rgb:-'], w * h * 3)
    m = bytearray(w * h)
    for i in range(w * h):
        r, g, b = d[3 * i], d[3 * i + 1], d[3 * i + 2]
        if r - b > 45 and (r * 299 + g * 587 + b * 114) // 1000 < 195:
            m[i] = 1
    return m, w, h


def pack_silhouette(path):
    """the drawn road network of a pack map, as a filled mask over BOX

    The dashed grid lines are the same hue as the outline and only a shade
    lighter, so a threshold cannot separate them -- but they are printed from a
    fixed template, and `Blank.png` IS that template with no map on it. Subtract
    it (dilated a pixel, for the resampling) and only the map is left.
    """
    global _TEMPLATE
    m, w, h = _brown(path)
    if _TEMPLATE is None:
        t, tw, th = _brown(ORIGINAL + TEMPLATE)
        _TEMPLATE = _dilate(t, tw, th, 1)
    for i in range(w * h):
        if _TEMPLATE[i]:
            m[i] = 0
    return _despeckle(_fill(_dilate(m, w, h, 2), w, h), w, h), w, h


def _fill(m, w, h):
    out = bytearray(w * h)
    q = deque()

    def seed(i):
        if not m[i] and not out[i]:
            out[i] = 1
            q.append(i)

    for x in range(w):
        seed(x); seed((h - 1) * w + x)
    for y in range(h):
        seed(y * w); seed(y * w + w - 1)
    while q:
        i = q.popleft()
        x = i % w
        if x:         seed(i - 1)
        if x < w - 1: seed(i + 1)
        if i >= w:            seed(i - w)
        if i < (h - 1) * w:   seed(i + w)
    return bytearray(0 if out[i] else 1 for i in range(w * h))


def _despeckle(m, w, h, least=60):
    """drop blobs too small to be a room -- grid dashes the template missed"""
    seen = bytearray(w * h)
    for i in range(w * h):
        if not m[i] or seen[i]:
            continue
        blob, q = [], deque([i])
        seen[i] = 1
        while q:
            j = q.popleft()
            blob.append(j)
            x = j % w
            for k, ok in ((j - 1, x), (j + 1, x < w - 1), (j - w, j >= w),
                          (j + w, j < (h - 1) * w)):
                if ok and m[k] and not seen[k]:
                    seen[k] = 1
                    q.append(k)
        if len(blob) < least:
            for j in blob:
                m[j] = 0
    return m


def art_mask(cfg, w=670, h=600, slack=2):
    """where the redrawn map has art, as a mask over the 670x600 canvas"""
    mask = bytearray(w * h)
    for piece in cfg['art']:
        # x/y/w/h is the box of the SOLID art, not of the glow around it
        art_w, art_h, art_x, art_y = solid_box(piece['tex'])
        alpha = subprocess.run(
            [CONVERT, GM_ART + piece['tex'] + '.png',
             '-crop', '%dx%d+%d+%d' % (art_w, art_h, art_x, art_y), '+repage',
             '-resize', '%dx%d!' % (piece['w'], piece['h']),
             '-alpha', 'extract', '-depth', '8', 'gray:-'],
            capture_output=True).stdout
        for y in range(piece['h']):
            row = piece['y'] + y
            if not 0 <= row < h:
                continue
            for x in range(piece['w']):
                col = piece['x'] + x
                if 0 <= col < w and alpha[y * piece['w'] + x] > 110:
                    mask[row * w + col] = 1
    for _ in range(slack):                      # a pin may sit a pixel proud
        grown = bytearray(mask)
        for y in range(1, h - 1):
            r = y * w
            for x in range(1, w - 1):
                if mask[r + x]:
                    grown[r + x - 1] = grown[r + x + 1] = 1
                    grown[r - w + x] = grown[r + w + x] = 1
        mask = grown
    return mask, w, h


def points():
    maps = {m['name']: m['img'].replace('images/maps/', '')
            for m in json.load(open(PACK + 'maps/maps.json'))}
    pts = {}
    for f in glob.glob(PACK + 'locations/*.json'):
        def walk(nodes):
            for x in nodes:
                for mp in x.get('map_locations') or []:
                    img = maps.get(mp['map'])
                    if img:
                        pts.setdefault(img, []).append(('pin', mp['x'], mp['y']))
                walk(x.get('children') or [])
        walk(json.load(open(f)))
    rooms = json.load(open(os.environ.get('ROOM_POS', PACK + 'tools/generated/room_positions.json')))
    for name, rs in rooms.items():
        img = maps.get(name)
        if img:
            for code, (x, y) in rs.items():
                pts.setdefault(img, []).append(('room ' + code, x, y))
    return pts


def mark(img, pts, out):
    src = BASELINE + img if os.path.exists(BASELINE + img) else MAPS_DIR + img
    cmd = [CONVERT, src, '-fill', 'none', '-stroke', 'red', '-strokewidth', '2']
    for kind, x, y in pts:
        cmd += ['-draw', 'circle %d,%d %d,%d' % (x, y, x + 9, y)]
    cmd += ['-stroke', 'none', '-fill', 'red', '-pointsize', '13']
    for kind, x, y in pts:
        cmd += ['-draw', 'text %d,%d "%s"' % (x + 12, y + 4, kind)]
    cmd.append(out + '/' + img)
    subprocess.run(cmd, stderr=subprocess.DEVNULL)


def drawn_maps():
    """The images render_maps makes -- the grid sheets are another tool's."""
    cfg = json.load(open(os.environ.get(
        'MAP_LAYOUT', PACK + 'tools/generated/map_layout.json')))
    return sorted(img for img, c in cfg.items() if c.get('art'))


def snapshot(force=False):
    """Copy the pack's current maps into _baseline/, asking before replacing."""
    have = sorted(os.path.basename(f) for f in glob.glob(BASELINE + '*.png'))
    if have and not force:
        answer = input('tools/verify/_baseline/ already holds %d maps. '
                       'Replace them? [y/N] ' % len(have)).strip().lower()
        if answer not in ('y', 'yes'):
            print('  kept the snapshot that was there')
            return False
    os.makedirs(BASELINE, exist_ok=True)
    for f in glob.glob(BASELINE + '*.png'):
        os.remove(f)
    copied = 0
    for img in drawn_maps() + [TEMPLATE]:
        src = MAPS_DIR + img
        if os.path.exists(src):
            shutil.copyfile(src, BASELINE + img)
            copied += 1
    print('snapshot: %d maps copied into tools/verify/_baseline/' % copied)
    return True


def rendered(into):
    """Render the maps as the tools would make them now."""
    os.makedirs(into, exist_ok=True)
    r = subprocess.run([sys.executable, PACK + 'tools/gamedata/render_maps.py',
                        '--out', into], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('render_maps failed:\n' + r.stderr[-600:])
    return sorted(os.path.basename(f) for f in glob.glob(into + '/*.png'))


def compare_art(fresh_dir):
    """Baseline image vs freshly rendered, per map."""
    base = sorted(os.path.basename(f) for f in glob.glob(BASELINE + '*.png'))
    if not base:
        print('no snapshot to compare against; run without --skip-copy')
        return 0
    differ, missing = [], []
    for img in base:
        made = fresh_dir + '/' + img
        if not os.path.exists(made):
            missing.append(img)
        elif open(BASELINE + img, 'rb').read() != open(made, 'rb').read():
            differ.append(img)
    print('art: %d maps compared, %d differ from the snapshot%s'
          % (len(base), len(differ),
             ', %d no longer rendered' % len(missing) if missing else ''))
    for img in differ + missing:
        print('    %s' % img)
    return len(differ) + len(missing)


def accepted():
    if os.path.exists(ACCEPTED):
        with open(ACCEPTED, encoding='utf-8') as fh:
            return {k: {tuple(p) for p in v} for k, v in json.load(fh).items()}
    return {}


def check_points(out=None, record=False):
    """Do the pins and room labels land on drawn art?

    Where _original holds the map this replaced, a point off the new art is a
    REGRESSION only if it was on drawn road there. Without it, the recorded
    list from the last run stands in, so a run only reports what is new.
    """
    cfg = json.load(open(os.environ.get(
        'MAP_LAYOUT', PACK + 'tools/generated/map_layout.json')))
    pts = points()
    known = accepted()
    off_now = {}
    parked = total = beside = new_off = old_off = 0
    for img in sorted(cfg):
        got = pts.get(img) or []
        if not got or not cfg[img]['art']:
            continue
        exempt = OFF_PATH.get(img, set())
        # a pin sharing a coordinate with an exempt label is exempt with it
        exempt_spots = {(x, y) for kind, x, y in got
                        if kind.startswith('room ') and kind[5:] in exempt}
        mask, w, h = art_mask(cfg[img])
        was = known.get(img, set())
        before = None
        if os.path.exists(ORIGINAL + img) and os.path.exists(ORIGINAL + TEMPLATE):
            before = pack_silhouette(ORIGINAL + img)
        fresh = []
        for kind, x, y in got:
            total += 1
            if kind == 'pin' and x == PARKED_X:
                parked += 1
            elif 0 <= x < w and 0 <= y < h and mask[y * w + x]:
                pass
            elif (x, y) in exempt or (x, y) in exempt_spots or kind[5:] in exempt:
                beside += 1
            elif before is not None:
                old, ow, oh = before
                ox, oy = x - BOX[0], y - BOX[1]
                if 0 <= ox < ow and 0 <= oy < oh and old[oy * ow + ox]:
                    fresh.append((kind, x, y))   # was on drawn road, is not now
                    new_off += 1
                else:
                    old_off += 1
            else:
                off_now.setdefault(img, set()).add((x, y))
                if (x, y) in was:
                    old_off += 1
                else:
                    fresh.append((kind, x, y))
                    new_off += 1
        if fresh:
            print('%-30s %d NEW points off the art: %s' % (img, len(fresh), fresh[:6]))
            if out:
                mark(img, fresh, out)
    against = 'the original maps' if os.path.isdir(ORIGINAL) and os.listdir(ORIGINAL) \
        else 'the list recorded last run'
    print('points: %d checked against %s -- %d parked aggregates, %d beside '
          'their corridor, %d already off, %d NEW'
          % (total, against, parked, beside, old_off, new_off))
    # Only worth recording when there is nothing better to compare against;
    # with _original present the silhouette is the authority.
    if record and not off_now:
        record = False
    if record:
        os.makedirs(BASELINE, exist_ok=True)
        with open(ACCEPTED, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({k: sorted(v) for k, v in sorted(off_now.items())},
                      fh, indent=1)
        print('  recorded %d accepted points alongside the snapshot'
              % sum(len(v) for v in off_now.values()))
    return new_off


def main():
    args = sys.argv[1:]
    out = None
    if '--mark' in args:
        out = args[args.index('--mark') + 1]
        os.makedirs(out, exist_ok=True)
    took = False
    if '--skip-copy' not in args:
        took = snapshot(force='--yes' in args)
    fresh = os.path.join(HERE, '_fresh')
    try:
        rendered(fresh)
        bad_art = compare_art(fresh)
    finally:
        shutil.rmtree(fresh, ignore_errors=True)
    bad_points = check_points(out, record=took)
    return 1 if (bad_art or bad_points) else 0


if __name__ == '__main__':
    sys.exit(main())

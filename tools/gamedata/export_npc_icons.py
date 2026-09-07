"""Cut the friendship and box icons out of the game bundle.

Portraits ship as two layers and the face layer is not one on its own -- for
half the cast the hair lives in the body layer. The head is cropped off
`NN_<NAME>_body_00`, the whole standing figure, instead.

The crop measures the head rather than taking a fixed fraction of the figure,
which wide shoulders throw off: trim the figure, take the bounding box of its
top quarter, cut a square a little wider than that. TUNED carries the six whose
coat or hat pads that band.

Ventuswill has no standing figure and her body layer no face, so hers is
composited in and framed on the face. That box is written down rather than
detected: the gap in the body art is not cleanly transparent.

Boxes are `MOBJ_BOX`, the crate texture the map objects use.

Barriers -- the seal across a doorway until the room's monsters are dead -- have
no texture of their own. `efc_mGen_wall_red` is a PARAMETER texture: red is a
flat 100% carrying no shape, while green, blue and alpha each hold a falloff for
the shader, so reading it as RGB gives a white-hot core the barrier never has.
The icon is assembled from the alpha instead -- as the intensity mask, mirrored
onto its own right edge for one symmetric arc, tinted amber, with a second arc
stacked a quarter above it.

`MOBJ_CLEAR_WALL` is empty and `MOBJ_FID_WALL_*` is field-dungeon rubble;
neither is the barrier.

    python3 tools/gamedata/export_npc_icons.py [bundle]
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# paths also pins SOURCE_DATE_EPOCH, so ImageMagick leaves the tIME chunk out
from paths import BUNDLE, CONVERT, PACK, need        # noqa: E402
SIZE = 128
BAND, WIDEN = 25, 1.18        # % of the figure to measure; head width -> crop side
TUNED = {                     # band %, head width -> crop side, judged by eye
    'Bado': (8, 1.7), 'Blossom': (8, 1.7), 'Dolce': (8, 1.7), 'Margaret': (8, 1.7),
    'Dylas': (8, 1.2), 'Porcoline': (25, 0.95),
}
NUDGE = {'Porcoline': -0.25}  # sideways shift as a fraction of the crop, his hat
                              # plumes pull the measured centre off his face
FACE_ZOOM = 2.2               # crop side as a multiple of a written-down face box
FACE_LIFT = 0.25              # ...raised by this much of it, to sit off the chin
BAR_W, BAR_H = 128, 64        # one barrier arc, mirrored from the mask
BAR_LIFT = BAR_H // 4         # the second arc sits a quarter of the pair above
BAR_AMBER = '#FFC572'         # (255,197,114), sampled off a barrier in game

ROSTER = {
    'Vishnal': '01_VIZNAR',      'Clorica': '02_CLORICA',
    'Volkanon': '03_VOLCANON',   'Forte': '04_FORTE',
    'Kiel': '05_KEEL',           'Bado': '06_BADO',
    'Margaret': '07_MARGUERITE', 'Dylas': '08_DIRUS',
    'Arthur': '09_ARTHUR',       'Porcoline': '10_POKORINU',
    'Xiao Pai': '11_SYAOPAI',    'Lin Fa': '12_RINFA',
    'Amber': '13_KOHAKU',        'Illuminata': '14_ELMINATA',
    'Doug': '15_DAG',            'Blossom': '16_BLOSSOM',
    'Dolce': '17_DOLCE',         'Jones': '18_JONES',
    'Nancy': '19_NANCY',         'Leon': '20_LEON',
    'Ventuswill': '21_SYELZA',
}
# name -> where its face layer sits on the 1024px body, as w,h,x,y. Measured off
# the art; only the characters whose body is drawn faceless need an entry.
FACE_BOX = {'Ventuswill': (200, 188, 372, 176)}


def slug(s):
    return s.lower().replace(' ', '')


def out(a):
    return subprocess.run(a, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True).stdout


def square(src, dst):
    """the art trimmed and fitted to a SIZE square on transparency"""
    subprocess.run([CONVERT, src, '-trim', '+repage', '-resize', '%dx%d' % (SIZE - 2, SIZE - 2),
                    '-background', '#00000000', '-gravity', 'center',
                    '-extent', '%dx%d' % (SIZE, SIZE), dst],
                   check=True, stderr=subprocess.DEVNULL)


def with_face(body, face, box, dst):
    """the body layer with its face dropped into place"""
    w, h, x, y = box
    subprocess.run([CONVERT, body, '(', face, '-trim', '+repage', '-resize', '%dx%d!' % (w, h), ')',
                    '-geometry', '+%d+%d' % (x, y), '-composite', dst],
                   check=True, stderr=subprocess.DEVNULL)


def head(src, dst, tmp, band=BAND, widen=WIDEN, nudge=0.0):
    """the head cut off the top of a standing figure"""
    t = tmp + '/trim.png'
    subprocess.run([CONVERT, src, '-trim', '+repage', t], check=True, stderr=subprocess.DEVNULL)
    w_all = int(out([CONVERT, t, '-format', '%w', 'info:']))
    bb = out([CONVERT, t, '-crop', '100%%x%d%%+0+0' % band, '+repage', '-format', '%@', 'info:'])
    w, _h, x, _y = (int(v) for v in bb.replace('x', ' ').replace('+', ' ').split())
    side = int(w * widen)
    x0 = max(0, min(w_all - side, x + w // 2 - side // 2 + int(side * nudge)))
    box = tmp + '/head.png'
    subprocess.run([CONVERT, t, '-crop', '%dx%d+%d+0' % (side, side, x0), '+repage', box],
                   check=True, stderr=subprocess.DEVNULL)
    square(box, dst)


def around_face(src, face_box, dst, tmp):
    """a square centred on a face whose position is known"""
    w, h, x, y = face_box
    side = int(w * FACE_ZOOM)
    x0 = max(0, x + w // 2 - side // 2)
    y0 = max(0, y + h // 2 - side // 2 - int(side * FACE_LIFT))
    box = tmp + '/face.png'
    subprocess.run([CONVERT, src, '-crop', '%dx%d+%d+%d' % (side, side, x0, y0), '+repage', box],
                   check=True, stderr=subprocess.DEVNULL)
    square(box, dst)


def barrier(src, dst, tmp):
    """two glow arcs, the layered seal the game raises across a doorway"""
    mask, arc, tint = tmp + '/mask.png', tmp + '/arc.png', tmp + '/tint.png'
    subprocess.run([CONVERT, src, '-alpha', 'extract', mask], check=True, stderr=subprocess.DEVNULL)
    subprocess.run([CONVERT, mask, '(', mask, '-flop', ')', '+append',
                    '-resize', '%dx%d!' % (BAR_W, BAR_H), arc],
                   check=True, stderr=subprocess.DEVNULL)
    subprocess.run([CONVERT, '-size', '%dx%d' % (BAR_W, BAR_H), 'xc:' + BAR_AMBER,
                    arc, '-alpha', 'off', '-compose', 'CopyOpacity', '-composite', tint],
                   check=True, stderr=subprocess.DEVNULL)
    foot = (SIZE - (BAR_H + BAR_LIFT)) // 2      # centre the pair in the square
    subprocess.run([CONVERT, '-size', '%dx%d' % (SIZE, SIZE), 'xc:#00000000', '-gravity', 'South',
                    '(', tint, ')', '-geometry', '+0+%d' % foot,
                    '-compose', 'over', '-composite',
                    '(', tint, ')', '-geometry', '+0+%d' % (foot + BAR_LIFT), '-composite',
                    dst], check=True, stderr=subprocess.DEVNULL)


def main():
    bundle = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(PACK + 'images/npc', exist_ok=True)

    def extract(pattern, into):
        cmd = [sys.executable, PACK + 'tools/gamedata/extract_textures.py', pattern, into]
        if bundle:
            cmd.append(bundle)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

    with tempfile.TemporaryDirectory() as tmp:
        extract(r'^(%s)_body_00\.texture$' % '|'.join(sorted(ROSTER.values())), tmp)
        extract(r'^(%s)_face_000_NORMAL\.texture$'
                % '|'.join(sorted(ROSTER[n] for n in FACE_BOX)), tmp)

        made = []
        for name, tex in sorted(ROSTER.items()):
            src = '%s/%s_body_00.png' % (tmp, tex)
            if not os.path.exists(src):
                continue
            dst = PACK + 'images/npc/%s.png' % slug(name)
            if name in FACE_BOX:
                whole = '%s/%s_whole.png' % (tmp, tex)
                with_face(src, '%s/%s_face_000_NORMAL.png' % (tmp, tex), FACE_BOX[name], whole)
                around_face(whole, FACE_BOX[name], dst, tmp)
            else:
                head(src, dst, tmp, *TUNED.get(name, (BAND, WIDEN)),
                     nudge=NUDGE.get(name, 0.0))
            made.append(name)
        print('villager portraits %3d of %d' % (len(made), len(ROSTER)))
        missing = sorted(set(ROSTER) - set(made))
        if missing:
            raise SystemExit('no portrait for %s' % missing)

        extract(r'^MOBJ_BOX\.texture$', tmp)
        square(tmp + '/MOBJ_BOX.png', PACK + 'images/items/box_closed.png')
        print('box crate          written')

        extract(r'^efc_mGen_wall_red\.texture$', tmp)
        barrier(tmp + '/efc_mGen_wall_red.png', PACK + 'images/items/barrier_closed.png', tmp)
        print('barrier seal       written')


if __name__ == '__main__':
    main()

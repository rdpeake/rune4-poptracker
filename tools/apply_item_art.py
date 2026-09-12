"""Copy the hand-drawn tiles in tools/art/items/<item code>.png over the
generated ones, for the items the game has no art for (the bridges, the
licences, "Level Up"). Pass 3 of three -- see "The three passes over a tile"
in tools/README.md.

The file name is the item's `codes` in items/items.json, so a drawing is wired
up by being named right. A name matching no item is an error, not a silent
skip: a typo'd slug would otherwise go unnoticed until somebody looked at the
panel.

    python3 tools/apply_item_art.py             do it
    python3 tools/apply_item_art.py --check     say what it would do, write nothing
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE) + '/'
ART = HERE + '/art/items'
SIZE = 128            # what export_item_tiles.py draws; a drawing must match


def png_size(path):
    """(width, height) straight out of the IHDR, no image library needed"""
    with open(path, 'rb') as fh:
        head = fh.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('%s is not a PNG' % path)
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def targets():
    """{item code: the pack-relative image it owns}, from items/items.json.

    Read rather than assumed to be images/items/<code>.png, because an item is
    free to point `img` somewhere else.
    """
    with open(PACK + 'items/items.json', encoding='utf-8') as fh:
        return {i['codes']: i['img'] for i in json.load(fh)
                if i.get('codes') and i.get('img')}


def main(check=False):
    img_of = targets()
    done = 0
    for name in sorted(os.listdir(ART)):
        if not name.endswith('.png'):
            continue
        code, src = name[:-len('.png')], os.path.join(ART, name)
        if code not in img_of:
            raise SystemExit('no item has the code %r -- rename the drawing in '
                             'tools/art/items to an item code from '
                             'items/items.json' % code)
        width, height = png_size(src)
        if (width, height) != (SIZE, SIZE):
            raise SystemExit('%s is %dx%d, wanted %dx%d'
                             % (name, width, height, SIZE, SIZE))
        if check:
            print('  %-24s -> %s' % (code, img_of[code]))
        else:
            shutil.copyfile(src, PACK + img_of[code])
        done += 1
    print('hand-drawn tiles %s %5d' % ('to copy' if check else 'copied', done))


if __name__ == '__main__':
    main('--check' in sys.argv)

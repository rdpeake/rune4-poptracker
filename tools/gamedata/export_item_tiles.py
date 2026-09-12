"""Rebuild images/items/*.png, putting the game's own icon on each item's tile.

The pack's tiles are generated (see tools/gen_item_tiles.mjs). Where the game has
art for an item, this puts that art on a white face inside a border in the item's
category colour, so the colour coding and the progression rim survive and only the
name text is replaced. Everything else keeps its text tile, unless somebody has
drawn one: tools/apply_item_art.py runs last and lays tools/art/items/<code>.png
over the result, which is how the ~70 AP-invented items (bridges, licences,
"Level Up") that the game has no art for at all get a picture.

Three things the extraction depends on, documented in tools/README.md
under Artwork:

  * the icons are BC7 inside a .texture container in bundleMain.mbundle
  * they come out a quarter turn over, so every one is rotated back
  * an item's icon is found by NAME in the game's own string table, not by
    position in the apworld's spreadsheet -- the sheet's categories are wider
    than the game's, so position drifts (its Fish list opens with Round Stone)

Needs the icons extracted by tools/gamedata/extract_textures.py and node for the tile
renderer. Nothing here writes outside images/items/.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import colorsys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# paths also pins SOURCE_DATE_EPOCH, so ImageMagick leaves the tIME chunk out
from paths import CONVERT, ICONS, PACK, need         # noqa: E402
sys.path.insert(0, os.path.dirname(HERE))
import apply_item_art                                # noqa: E402
SIZE, BAND, PAD, R_OUT, R_IN = 128, 10, 7, 22, 12


def lift(hexcolour, k=0.18):
    """Nudge a tile colour lighter and a touch more saturated.

    The shipped colours are dark because they filled the whole tile. Once the
    colour is only a border they disappear against a dark panel, and the border
    is the only thing left carrying the category.
    """
    h = hexcolour.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, min(.9, ll + k), min(1., ss * 1.15))
    return '#%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))


PALETTE = json.load(open(PACK + 'tools/item_palette.json', encoding='utf-8'))
META = json.load(open(PACK + 'tools/generated/item_meta.json', encoding='utf-8'))


def colours(code):
    """(border, rim) for an item, from its category and classification.

    Both are looked up, never read back off the tile being replaced: sampling
    the file about to be overwritten made the colour depend on the last run,
    and once a tile carried an icon the dominant colour was the white face, so
    every family collapsed to the same grey.
    """
    meta = META.get('items', {}).get(code) or {}
    family = PALETTE['family'].get(meta.get('cat'), 'neutral')
    border = PALETTE['palette'][family][0]
    rim = PALETTE['rim'].get(meta.get('cls'), PALETTE['rim']['filler'])
    return lift(border), rim


SETTING_BG = lift(PALETTE['palette']['slate'][0])


def tame_colours(slug):
    """(border, rim) for a monster tile, from its tame tier.

    A tame's tile is coloured by tier rather than by any category, six colours
    over eleven tiers, so tier 0 and 6 share one and so on. A monster with no
    tame row is a boss: its own colour, and the gold rim they were given when
    the tiles were first drawn.
    """
    tier = META.get('tames', {}).get(slug)
    if tier is None:
        return lift(PALETTE['tame_boss']), PALETTE['rim']['boss']
    tiers = PALETTE['tame_tier']
    return lift(tiers[tier % len(tiers)]), PALETTE['rim']['filler']


_FACES = {}
_FACEDIR = None


def face(bg, rim):
    """the empty tile for one colour pair, drawn once and kept

    Every item takes its (fill, rim) from the palette, so across a full run
    there are barely a dozen distinct pairs for a thousand-odd tiles. Drawing
    the rounded rectangle per tile is that many redundant ImageMagick runs.
    """
    global _FACEDIR
    if (bg, rim) not in _FACES:
        if _FACEDIR is None:
            _FACEDIR = tempfile.mkdtemp(prefix='rf4tiles')
        out = os.path.join(_FACEDIR, '%d.png' % len(_FACES))
        subprocess.run([CONVERT, '-size', '%dx%d' % (SIZE, SIZE), 'xc:none',
                        '-stroke', rim, '-strokewidth', '2',
                        '-fill', bg, '-draw',
                        'roundrectangle 1,1,%d,%d,%d,%d' % (SIZE-2, SIZE-2, R_OUT, R_OUT),
                        '-stroke', 'none',
                        '-fill', '#ffffff', '-draw',
                        'roundrectangle %d,%d,%d,%d,%d,%d'
                        % (BAND, BAND, SIZE-1-BAND, SIZE-1-BAND, R_IN, R_IN), out],
                       stderr=subprocess.DEVNULL)
        _FACES[(bg, rim)] = out
    return _FACES[(bg, rim)]


def blank(bg, rim, out):
    """the tile with nothing on its face -- for items the game itself draws empty"""
    shutil.copyfile(face(bg, rim), out)


def tile(icon, bg, rim, out):
    inner, tmp = SIZE - 2 * BAND, out + '.tmp.png'
    subprocess.run([CONVERT, icon, '-trim', '+repage',
                    '-resize', '%dx%d' % (inner - 2 * PAD, inner - 2 * PAD),
                    '-background', 'none', '-gravity', 'center',
                    '-extent', '%dx%d' % (inner, inner), tmp],
                   stderr=subprocess.DEVNULL)
    subprocess.run([CONVERT, face(bg, rim), tmp, '-gravity', 'center', '-composite', out],
                   stderr=subprocess.DEVNULL)
    os.path.exists(tmp) and os.remove(tmp)


def main():
    icons = sys.argv[1] if len(sys.argv) > 1 else need(ICONS)
    plan = json.load(open(PACK + 'tools/item_icons.json', encoding='utf-8'))
    items = json.load(open(PACK + 'items/items.json', encoding='utf-8'))
    items = items if isinstance(items, list) else items['items']
    img_of = apply_item_art.targets()
    made = skipped = 0
    for code, stem in sorted(plan['items'].items()):
        src, dst = icons + stem + '.png', PACK + img_of.get(code, '')
        if not (os.path.exists(src) and code in img_of):
            skipped += 1
            continue
        bg, rim = colours(code)
        tile(src, bg, rim, dst)
        made += 1
    # the tame sheets draw monster portraits; same tile treatment so the pack
    # reads as one set
    mon = plan.get('monsters', {})
    mmade = 0
    for slug, face in sorted(mon.items()):
        src = icons + '../faces/' + face + '.png'
        dst = PACK + 'images/monsters/%s.png' % slug
        if not (os.path.exists(src) and os.path.exists(dst)):
            continue
        bg, rim = tame_colours(slug)
        tile(src, bg, rim, dst)
        mmade += 1
    if mmade:
        print('monster portraits             %5d' % mmade)

    # the settings toggles are their own file too, and each gates a category the
    # game already has an icon for
    op = json.load(open(PACK + 'items/options.json', encoding='utf-8'))
    ops = op if isinstance(op, list) else op['items']
    omade = 0
    for o in ops:
        stem = plan.get('options', {}).get(o.get('codes'))
        src = icons + (stem or '') + '.png'
        if not stem or not os.path.exists(src):
            continue
        dst = PACK + 'images/settings/%s.png' % o['codes']
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tile(src, SETTING_BG, PALETTE['rim']['filler'], dst)
        o['img'] = 'images/settings/%s.png' % o['codes']
        omade += 1
    if omade:
        open(PACK + 'items/options.json', 'w', encoding='utf-8', newline='\n').write(
            json.dumps(op, indent=4, ensure_ascii=False) + '\n')
        print('option toggles given an icon %5d' % omade)

    # the request toggles live in their own file and all share one generic icon
    ev = json.load(open(PACK + 'items/events.json', encoding='utf-8'))
    evs = ev if isinstance(ev, list) else ev['items']
    by_name = {e['name']: e for e in evs}
    rmade = 0
    for name, spec in sorted(plan.get('requests', {}).items()):
        e = by_name.get(name)
        src = icons + spec['icon'] + '.png'
        if not e or not os.path.exists(src):
            continue
        dst = PACK + 'images/events/req_%s.png' % re.sub(r'[^a-z0-9]+', '',
                                                         name.lower())
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tile(src, lift('#3a3f4a'), 'rgba(255,255,255,0.22)', dst)
        rel = dst[len(PACK):]
        e['img'] = e['disabled_img'] = rel
        rmade += 1
    if rmade:
        open(PACK + 'items/events.json', 'w', encoding='utf-8', newline='\n').write(
            json.dumps(ev, indent=4, ensure_ascii=False) + '\n')
    # items with no art at all still get the tile, just an empty face, so the
    # set stays visually consistent instead of dropping back to a word
    empty = 0
    for name in plan.get('blank', []):
        code = next((i['codes'] for i in items if i['name'] == name), None)
        dst = PACK + img_of.get(code, '') if code else ''
        if not code or not os.path.exists(dst):
            continue
        bg, rim = colours(code)
        blank(bg, rim, dst)
        empty += 1
    if empty:
        print('blank tiles (game draws none) %5d' % empty)
    print('tiles rebuilt with game art %5d' % made)
    print('requests given an icon      %5d' % rmade)
    print('left as text                %5d' % (len(items) - made))
    if skipped:
        print('planned but no icon file    %5d' % skipped)
    if _FACEDIR:
        shutil.rmtree(_FACEDIR, ignore_errors=True)
    # last word goes to anything drawn by hand -- see tools/apply_item_art.py
    apply_item_art.main()


if __name__ == '__main__':
    main()

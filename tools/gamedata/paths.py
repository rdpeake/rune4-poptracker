"""Where the game's own files live: tools/gamedata/_input/, which is gitignored.

Only one file has to be found by hand:

    _input/bundleMain.mbundle     from a Rune Factory 4 Special install

`extract_textures.py` unpacks the rest out of it into the same folder:

    _input/art/                   mini_map_* minimap textures
    _input/icons/                 item icons
    _input/frame/bg_map_03.png    the panel the maps are drawn in
    _input/font/                  the caption face
    _input/rf3MapMiniPos.bin      where each room sits on its minimap

None of it is redistributed with the pack. Every path is resolved through
`need()`, so a missing file says which one and where to put it rather than
failing somewhere further in.

The tools the pack shells out to live here too, for the same reason: a box
where ImageMagick is named something else should say so rather than raise a
bare FileNotFoundError from whichever step happened to run first.
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
INPUT = os.path.join(HERE, '_input') + '/'

BUNDLE = INPUT + 'bundleMain.mbundle'
MINIPOS = INPUT + 'rf3MapMiniPos.bin'
ART = INPUT + 'art/'
ICONS = INPUT + 'icons/'
FRAME = INPUT + 'frame/bg_map_03.png'
FONT = INPUT + 'font/CormorantSC-SemiBold.ttf'

# The face the map labels are drawn in -- a system font, not one from the game.
LABEL_FONT = os.environ.get(
    'LABEL_FONT', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')

# ImageMagick stamps a tIME chunk into every PNG it writes, so an identical
# rebuild produces different bytes and every icon shows as changed.
# SOURCE_DATE_EPOCH makes it leave the chunk out. Set on import, since every
# tool that draws anything reaches this module before it draws.
os.environ.setdefault('SOURCE_DATE_EPOCH', '0')


def _convert():
    """ImageMagick 6's CLI, which Debian renames to keep it clear of v7"""
    named = os.environ.get('CONVERT')
    if named:
        return named
    debian = '/usr/bin/convert-im6.q16'
    if os.path.exists(debian):
        return debian
    for name in ('convert-im6.q16', 'convert', 'magick'):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        'ImageMagick not found.\n'
        '  Install it (Debian: apt install imagemagick), or point CONVERT at it:\n'
        '      CONVERT=/path/to/convert python3 tools/...')


CONVERT = _convert()


def need(path, what=''):
    """Return path, or explain what is missing and where it goes."""
    if os.path.exists(path):
        return path
    rel = os.path.relpath(path, PACK)
    raise SystemExit(
        '%s not found.\n  Put it at %s%s\n'
        '  Everything but bundleMain.mbundle comes out of the bundle:\n'
        '      python3 tools/gamedata/extract_textures.py'
        % (os.path.basename(path.rstrip('/')) or rel, rel,
           '  (%s)' % what if what else ''))

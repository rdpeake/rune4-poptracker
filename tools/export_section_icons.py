"""Give every check its own icon in the tracker instead of one shared crate.

The pack already draws the right picture for every shipment and tame on the
grid sheets, so the sections point at those same tiles.

Friendship, box, barrier and search checks are set on the LOCATION rather than
each section: all ten of a villager's heart levels want the same portrait, and
every room's box wants the same crate, so one image per node beats ten identical
ones. A section with no image of its own inherits the location's
(locationsection.cpp:61). The search icon is the game's own I_Catecory08.

Everything else resolves at the *section*, not the location: a section may
carry its own `chest_unopened_img`, and `MapTooltip` looks the image up on the
section a `ref` points AT (maptooltip.cpp:145), so setting it on the canonical
section in the region file reaches the grid-sheet pins too. Map markers are
drawn as coloured shapes and never use these images at all.

The opened icon is the closed one darkened, the relationship the crate, chest
and paw pairs already have (~72% brightness).

    python3 tools/export_section_icons.py
"""
import collections
import glob
import re
import json
import os
import subprocess
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
sys.path.insert(0, PACK + 'tools')
sys.path.insert(0, PACK + 'tools/gamedata')
# paths also pins SOURCE_DATE_EPOCH, so ImageMagick leaves the tIME chunk out
from paths import CONVERT                            # noqa: E402
from export_grid_maps import item_art, monster_art    # noqa: E402

OPEN_BRIGHTNESS = 72
KINDS = (('Shipment', 'images/items'), ('Tame', 'images/monsters'))
BOX = 'images/items/box_closed.png'
BARRIER = 'images/items/barrier_closed.png'
SEARCH = 'images/items/search_closed.png'
# what a check IS decides its art, and generated/location_kinds.json says so for
# every one of them -- no reading it out of the wording of a node name
NODE_IMG = {'box': BOX, 'barrier': BARRIER, 'search': SEARCH}
SECTION_ART = {'shipment': 'Shipment', 'tame': 'Tame'}


def node_kinds():
    """{node path: loc_type}, for a node whose checks agree on one kind."""
    kinds = json.load(open(PACK + 'tools/generated/location_kinds.json',
                           encoding='utf-8'))
    text = open(PACK + 'scripts/autotracking/location_mapping.lua',
                encoding='utf-8').read()
    seen = collections.defaultdict(set)
    for apid, path in re.findall(r'\[(\d+)\]\s*=\s*\{"([^"]+)"', text):
        if apid in kinds:
            seen['/'.join(path.lstrip('@').split('/')[:-1])].add(kinds[apid])
    return {node: one.pop() for node, one in seen.items() if len(one) == 1}


def dimmed(img):
    """the darkened twin of a tile, made once and cached on disk"""
    d, f = os.path.split(img)
    out = '%s/open/%s' % (d, f)
    if not os.path.exists(PACK + out):
        os.makedirs(PACK + d + '/open', exist_ok=True)
        subprocess.run([CONVERT, PACK + img, '-modulate', str(OPEN_BRIGHTNESS), PACK + out],
                       check=True)
    return out


def main():
    art = {'Shipment': item_art(), 'Tame': monster_art()}

    npc = {f[:-4]: 'images/npc/' + f for f in os.listdir(PACK + 'images/npc')
           if f.endswith('.png')} if os.path.isdir(PACK + 'images/npc') else {}

    of_node = node_kinds()
    done = {k: 0 for k in list(SECTION_ART.values()) + ['Villager'] +
            [n.title() for n in NODE_IMG]}
    missing, opened = [], set()
    for path in sorted(glob.glob(PACK + 'locations/*.json')):
        doc = json.load(open(path, encoding='utf-8'))
        touched = False

        def walk(node, trail):
            nonlocal touched
            here = trail + [str(node.get('name') or '')]
            kind = of_node.get('/'.join(here))
            img = (NODE_IMG.get(kind) if kind != 'friendship'
                   else npc.get(here[-1].lower().replace(' ', '')))
            if img:
                node['chest_unopened_img'] = '/' + img
                node['chest_opened_img'] = '/' + dimmed(img)
                opened.add(img)
                done['Villager' if kind == 'friendship' else kind.title()] += 1
                touched = True
            named = SECTION_ART.get(kind)
            for sec in (node.get('sections') or []):
                if named is None or 'ref' in sec or not sec.get('name'):
                    continue
                img = art[named](sec['name'])
                if not img:
                    missing.append((named, sec['name']))
                    continue
                sec['chest_unopened_img'] = '/' + img
                sec['chest_opened_img'] = '/' + dimmed(img)
                opened.add(img)
                done[named] += 1
                touched = True
            for c in (node.get('children') or []):
                walk(c, here)

        for root in (doc if isinstance(doc, list) else [doc]):
            walk(root, [])
        if touched:
            # indent 4, no ASCII escaping, trailing newline: what export_barriers.py
            # and apply_rules.py write, so the three tools stop flipping the files
            txt = json.dumps(doc, indent=4, ensure_ascii=False)
            open(path, 'w', encoding='utf-8', newline='\n').write(txt + '\n')

    for kind in sorted(done):
        print('%-10s given its own icon %5d' % (kind, done[kind]))
    print('darkened twins on disk                %5d' % len(opened))
    if missing:
        raise SystemExit('no art for %d sections, e.g. %s' % (len(missing), missing[:4]))


if __name__ == '__main__':
    main()

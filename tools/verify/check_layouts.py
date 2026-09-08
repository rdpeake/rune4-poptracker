"""Check the pack's four arrangements still show the same things.

PopTracker picks `tracker_horizontal` for a window wider than it is tall and
`tracker_vertical` otherwise, the Items Only variant swaps the body inside
whichever it picked, and the chroma option swaps the background around it.
That is one set of tabs and items drawn four ways, hand-written across seven
files, so a map or an item added to one is easy to leave out of another --
`Forest of Beginnings` reached the landscape map tabs in 35541f2 and the
portrait ones only much later.

    tabs.json    tabbed_maps_horizontal   vs  tabbed_maps_vertical
    items.json   shared_item_grid_*       same items, reflowed 30/16/12 wide
    events.json  event_grid*              same items, reflowed 21/11/9 wide
    tracker.json vs chroma_on/chroma_off  the same roots, bar the background
    every layouts/*.json                  no reference to a key nothing defines
    every itemgrid                        no code items/ does not define
    maps.json                             every map on a tab, every tab a map

A grid cell naming a code nothing defines draws as a blank square and says
nothing, which is how half of an item rename hides: `Clippers` carried the code
`progression` until upstream fixed its name, and four hand-maintained files had
to move together.

The map tab trees must match exactly, titles and order included: they show the
same maps, only in a differently shaped pane. The grids must hold the same
items in the same order, but NOT the same rows -- `tools/reflow_item_grids.py`
wraps them at each layout's own width.

Usage:  python3 tools/verify/check_layouts.py
Non-zero exit if any of them drift.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'

ROOTS = ('tracker_default', 'tracker_horizontal', 'tracker_vertical',
         'tracker_broadcast')
ITEM_FILES = ('items/items.json', 'items/events.json', 'items/options.json')
# scripts/logic_info.lua builds this one at runtime, so no items/ file has it
LUA_CODES = ('LOGIC_INFO_CODE',)


def walk(node, out, path=''):
    """Depth-first over a layout, collecting the leaves it draws."""
    if isinstance(node, list):
        for child in node:
            walk(child, out, path)
        return out
    if not isinstance(node, dict):
        return out
    if node.get('type') == 'tabbed':
        for tab in node.get('tabs', []):
            here = path + '/' + tab.get('title', '?')
            out.append(('tab', here, None))
            walk(tab.get('content'), out, here)
        return out
    if node.get('type') == 'map':
        for name in node.get('maps', []):
            out.append(('map', path, name))
    if node.get('type') == 'itemgrid':
        for row in node.get('rows', []):
            for code in row:
                out.append(('item', path, code))
    if node.get('type') == 'layout':
        out.append(('ref', path, node.get('key')))
    for key in ('content', 'tabs'):
        if key in node:
            walk(node[key], out, path)
    return out


def leaves(layout, kind):
    return [(path, name) for k, path, name in walk(layout, []) if k == kind]


def agree(what, kind, named, ordered=True):
    """Print how a set of layouts compare; return the number of differences."""
    first, want = named[0][0], leaves(named[0][1], kind)
    bad = 0
    for name, layout in named[1:]:
        got = leaves(layout, kind)
        if got == want:
            continue
        if not ordered and sorted(got) == sorted(want):
            continue
        for path, item in [x for x in want if x not in got]:
            print('  MISSING FROM %-14s %s%s'
                  % (name, path, ' -> ' + item if item else ''))
        for path, item in [x for x in got if x not in want]:
            print('  ONLY IN %-19s %s%s'
                  % (name, path, ' -> ' + item if item else ''))
        if got != want and sorted(got) == sorted(want):
            print('  %s holds the same %s as %s in a different order'
                  % (name, kind, first))
        bad += 1
    if not bad:
        print('  %-24s %d, same in all %d' % (what, len(want), len(named)))
    return bad


def named(layouts, keys):
    return [(key, layouts[key]) for key in keys if key in layouts]


def load(path):
    return json.load(open(PACK + path, encoding='utf-8'))


def main():
    bad = 0
    tabs = load('layouts/tabs.json')
    items = load('layouts/items.json')
    events = load('layouts/events.json')

    print('Map tabs')
    maps = named(tabs, ('tabbed_maps_horizontal', 'tabbed_maps_vertical'))
    bad += agree('tabs', 'tab', maps)
    bad += agree('maps', 'map', maps)

    print('Item grid')
    grids = named(items, ('shared_item_grid_horizontal',
                          'shared_item_grid_narrow',
                          'shared_item_grid_vertical'))
    bad += agree('tabs', 'tab', grids)
    bad += agree('items', 'item', grids, ordered=False)

    print('Request grid')
    bad += agree('items', 'item',
                 named(events, ('event_grid_horizontal', 'event_grid_narrow',
                                'event_grid')), ordered=False)

    print('Tracker roots')
    files = ['layouts/tracker.json', 'layouts/chroma_off.json',
             'layouts/chroma_on.json']
    plain = []
    for path in files:
        loaded = load(path)
        plain.append({root: json.dumps(
            {k: v for k, v in loaded[root].items() if k != 'background'},
            sort_keys=True) for root in ROOTS if root in loaded})
    for path, roots in zip(files[1:], plain[1:]):
        for root in ROOTS:
            if roots.get(root) != plain[0].get(root):
                print('  %-24s %s differs from tracker.json'
                      % (os.path.basename(path), root))
                bad += 1
    missing = [root for root in ROOTS if root not in plain[0]]
    for root in missing:
        print('  NOT DEFINED              %s' % root)
    bad += len(missing)
    if not missing and all(roots == plain[0] for roots in plain):
        print('  %-24s %d, same in all %d bar the background'
              % ('roots', len(ROOTS), len(files)))

    print('Layout references')
    defined, wanted = set(), {}
    for path in sorted(glob.glob(PACK + 'layouts/*.json')):
        loaded = json.load(open(path, encoding='utf-8'))
        defined |= set(loaded)
        for key, layout in loaded.items():
            for _, ref in leaves(layout, 'ref'):
                wanted.setdefault(ref, set()).add(
                    '%s/%s' % (os.path.basename(path), key))
    for ref in sorted(set(wanted) - defined):
        print('  NOTHING DEFINES          %s, wanted by %s'
              % (ref, ', '.join(sorted(wanted[ref]))))
        bad += 1
    if not set(wanted) - defined:
        print('  %-24s %d, all defined' % ('keys referenced', len(wanted)))

    print('Item codes')
    codes = set()
    for path in ITEM_FILES:
        loaded = load(path)
        for item in (loaded if isinstance(loaded, list) else loaded['items']):
            codes |= {c.strip() for c in (item.get('codes') or '').split(',')
                      if c.strip()}
    lua = open(PACK + 'scripts/logic_info.lua', encoding='utf-8').read()
    for name in LUA_CODES:
        found = re.search(r'%s = "([^"]+)"' % name, lua)
        if found:
            codes.add(found.group(1))
    drawn = {name for layout in (items, events)
             for key in layout
             for _, name in leaves(layout[key], 'item')}
    for code in sorted(drawn - codes):
        print('  NO SUCH ITEM             %s' % code)
    bad += len(drawn - codes)
    if not drawn - codes:
        print('  %-24s %d drawn, all defined' % ('item codes', len(drawn)))

    print('Maps')
    declared = {m['name'] for m in load('maps/maps.json')}
    shown = {name for _, name in leaves(tabs['tabbed_maps_horizontal'], 'map')}
    for name in sorted(shown - declared):
        print('  NO SUCH MAP              %s' % name)
    for name in sorted(declared - shown):
        print('  ON NO TAB                %s' % name)
    bad += len(shown ^ declared)
    if not shown ^ declared:
        print('  %-24s %d, each on a tab' % ('declared maps', len(declared)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

"""Check the portrait layout still shows everything the landscape one does.

The pack draws the same tracker twice: PopTracker picks `tracker_horizontal`
for a window wider than it is tall and falls back to `tracker_default` --
this pack's portrait arrangement -- otherwise. The two are hand-written and
sit in different halves of the same file, so a map or an item added to one is
easy to leave out of the other. `Forest of Beginnings` was added to the
landscape map tabs in 35541f2 and missing from portrait until this check.

    tabs.json     tabbed_maps_horizontal   vs  tabbed_maps_vertical
    items.json    shared_item_grid_*       same items, reflowed 30 or 12 wide
    maps.json     every map reachable from a tab, every tab's map declared

The map tab trees must match exactly, titles and order included: they show
the same maps, only in a differently shaped pane. The item grids must hold
the same items in the same tabs, but NOT the same rows -- portrait wraps at
12 columns and landscape at 30, so only the flattened set is compared.

Usage:  python3 tools/verify/check_layouts.py
Non-zero exit if the two drift.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'


def walk(node, out, path=''):
    """Depth-first over a layout, collecting the tabbed leaves it draws."""
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
    for key in ('content', 'tabs'):
        if key in node:
            walk(node[key], out, path)
    return out


def report(what, tall, wide, ordered):
    """Print one comparison; return the number of differences."""
    if ordered and tall == wide:
        print('  %-22s %d, in the same order' % (what, len(tall)))
        return 0
    only_wide = [x for x in wide if x not in tall]
    only_tall = [x for x in tall if x not in wide]
    if not only_wide and not only_tall:
        print('  %-22s %d, same set in a different order'
              % (what, len(set(tall))))
        return 0 if not ordered else 1
    for path, name in only_wide:
        print('  MISSING FROM PORTRAIT  %s%s'
              % (path, ' -> ' + name if name else ''))
    for path, name in only_tall:
        print('  MISSING FROM LANDSCAPE %s%s'
              % (path, ' -> ' + name if name else ''))
    return len(only_wide) + len(only_tall)


def main():
    tabs = json.load(open(PACK + 'layouts/tabs.json', encoding='utf-8'))
    items = json.load(open(PACK + 'layouts/items.json', encoding='utf-8'))
    maps = json.load(open(PACK + 'maps/maps.json', encoding='utf-8'))

    tall = walk(tabs['tabbed_maps_vertical'], [])
    wide = walk(tabs['tabbed_maps_horizontal'], [])
    bad = 0
    print('Map tabs')
    for kind, ordered in (('tab', True), ('map', True)):
        bad += report(kind + 's',
                      [(p, n) for k, p, n in tall if k == kind],
                      [(p, n) for k, p, n in wide if k == kind], ordered)

    tall = walk(items['shared_item_grid_vertical'], [])
    wide = walk(items['shared_item_grid_horizontal'], [])
    print('Item grid')
    bad += report('tabs', [(p, n) for k, p, n in tall if k == 'tab'],
                  [(p, n) for k, p, n in wide if k == 'tab'], True)
    bad += report('items', [(p, n) for k, p, n in tall if k == 'item'],
                  [(p, n) for k, p, n in wide if k == 'item'], False)

    print('Maps')
    declared = {m['name'] for m in maps}
    shown = {n for k, _, n in walk(tabs['tabbed_maps_horizontal'], [])
             if k == 'map'}
    for name in sorted(shown - declared):
        print('  NO SUCH MAP            %s' % name)
    for name in sorted(declared - shown):
        print('  ON NO TAB              %s' % name)
    bad += len(shown ^ declared)
    if not shown ^ declared:
        print('  %-22s %d, each on a tab' % ('declared maps', len(declared)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

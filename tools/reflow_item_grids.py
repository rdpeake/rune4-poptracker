"""Flow the item grid to the width each layout has room for.

`layouts/items.json` carries the same 12 tabs of items three times over, once
per shape the panel is drawn in, and the copies differ only in where the rows
break:

    shared_item_grid_horizontal   30 wide   the bottom strip in landscape
    shared_item_grid_narrow       16 wide   the bottom strip in portrait
    shared_item_grid_vertical     12 wide   the left column, and Items Only

That is 1138 items to keep in step by hand. The landscape grid is the source:
this reads its tabs in order and rewrites the other two by wrapping that
sequence at their own width.

The Requests grids are the same idea but generated, not hand-written --
`tools/apworld/export_requests.py` writes all three of them.

    python3 tools/reflow_item_grids.py            rewrite the narrow ones
    python3 tools/reflow_item_grids.py --check    fail if they have drifted

An item is added by putting it in the landscape grid, in the tab and at the
position it belongs, and running this. A tab added or renamed there is carried
over too, so the three always show the same 12.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE) + '/'

# file -> source key -> {key it writes: (items to a row, item size)}
FLOWS = {
    'layouts/items.json': ('shared_item_grid_horizontal', {
        'shared_item_grid_horizontal': (30, '32,32'),
        'shared_item_grid_narrow': (16, '32,32'),
        'shared_item_grid_vertical': (12, '32,32'),
    }),
}


def grids_of(node):
    """Every itemgrid in a layout, outermost first."""
    if isinstance(node, list):
        return [g for child in node for g in grids_of(child)]
    if not isinstance(node, dict):
        return []
    if node.get('type') == 'itemgrid':
        return [node]
    return [g for value in node.values() for g in grids_of(value)]


def flat(layout):
    """[(tab title or None, [item code])] for one grid, row breaks dropped."""
    titles = [tab['title'] for tab in layout['tabs']] \
        if layout.get('type') == 'tabbed' else [None]
    return [(title, [code for row in grid['rows'] for code in row])
            for title, grid in zip(titles, grids_of(layout))]


def wrap(tabs, width, size, tabbed, template):
    """`tabs` redrawn `width` items to a row, in the template's own frame."""
    def grid(codes):
        # built off the source grid itself, key order and all, so reflowing an
        # unchanged grid gives the same bytes back
        rows = [codes[i:i + width] for i in range(0, len(codes), width)]
        return {key: size if key == 'item_size' else
                rows if key == 'rows' else value
                for key, value in template.items()}

    if tabbed:
        return {'type': 'tabbed',
                'tabs': [{'title': title, 'content': grid(codes)}
                         for title, codes in tabs]}
    return {'type': 'array', 'orientation': 'vertical', 'margin': '0,0',
            'content': [grid(tabs[0][1])]}


def reflow(path, source, targets, check):
    """Rewrite one file's grids from its source grid. Returns a fault count."""
    was = open(PACK + path, encoding='utf-8').read()
    layouts = json.loads(was)
    tabs = flat(layouts[source])
    tabbed = layouts[source].get('type') == 'tabbed'
    # the source's own frame, so a change to margin or alignment carries over
    template = grids_of(layouts[source])[0]

    faults = 0
    for key in targets:
        # A grid holding something other than the source's items in the
        # source's order was edited directly; say so rather than quietly
        # throwing that edit away.
        if key in layouts and key != source and flat(layouts[key]) != tabs:
            print('  %s is not %s reflowed' % (key, source))
            faults += 1
    for key, (width, size) in targets.items():
        layouts[key] = wrap(tabs, width, size, tabbed, template)

    now = json.dumps(layouts, indent=4) + ('\n' if was.endswith('\n') else '')
    shape = ', '.join('%d wide %d rows' % (width, max(
        len(grid['rows']) for grid in grids_of(layouts[key])))
        for key, (width, _) in targets.items())
    print('%-20s %4d items over %2d tab(s) -- %s'
          % (os.path.basename(path), sum(len(c) for _, c in tabs), len(tabs),
             shape))
    if now == was:
        return faults
    if check:
        print('  OUT OF STEP -- run tools/reflow_item_grids.py')
        return faults + 1
    open(PACK + path, 'w', encoding='utf-8').write(now)
    print('  rewrote %s' % path)
    return faults


def main(check):
    bad = 0
    for path, (source, targets) in FLOWS.items():
        bad += reflow(path, source, targets, check)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))

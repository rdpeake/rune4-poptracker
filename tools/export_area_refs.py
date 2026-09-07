"""Make each area pin cover everything through the door.

The pin on an area's entrance -- `Autumn Road/Leon Karnak`, `Leon Karnak/Rune
Prana` -- is a node whose sections are all `ref`s into that area, so it shows how
much of the place behind the door is left. The lists were written by hand and
went stale the moment the barrier, box and search checks arrived: the Rune Prana
pin covered 81 of its 183 sections and said nothing about the other 102.

They are rebuilt here from the tree itself, in the order the area draws them, so
every floor and every sub-room lands on the pin that leads to it.

An area pin is recognised by what it already is: every section a `ref`, and all
of them into the one area the node is NAMED after. That is what separates it
from the grid-sheet pins, which are also all-ref but refer to one section and are
not named for its area.

    python3 tools/export_area_refs.py            report
    python3 tools/export_area_refs.py --write    apply
"""
import glob
import json
import os
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'


def sections_of(nodes, trail):
    """every real (non-ref) section under these nodes, in document order"""
    out = []
    for x in nodes:
        here = trail + [str(x.get('name') or '')]
        secs = x.get('sections') or []
        if not (secs and all('ref' in s for s in secs)):
            for s in secs:
                if 'ref' not in s:
                    out.append('/'.join(here + [str(s.get('name') or '')]))
        out += sections_of(x.get('children') or [], here)
    return out


def area_pins(doc, trail=()):
    """the nodes that are an area's entrance pin, with the area they lead to"""
    out = []
    for x in doc:
        here = tuple(trail) + (str(x.get('name') or ''),)
        secs = x.get('sections') or []
        if secs and all('ref' in s for s in secs):
            areas = {s['ref'].split('/')[0] for s in secs}
            if len(areas) == 1 and here[-1] == next(iter(areas)):
                out.append((here, x, here[-1]))
        out += area_pins(x.get('children') or [], here)
    return out


def main():
    docs = {p: json.load(open(p, encoding='utf-8'))
            for p in sorted(glob.glob(PACK + 'locations/*.json'))}

    whole = {}
    for doc in docs.values():
        for top in doc:
            name = str(top.get('name') or '')
            whole[name] = sections_of([top], [])

    changed = grew = 0
    for path, doc in docs.items():
        for here, node, area in area_pins(doc):
            want = whole.get(area)
            if want is None:
                continue
            had = [s['ref'] for s in node['sections'] if 'ref' in s]
            if had == want:
                continue
            changed += 1
            grew += len(want) - len(had)
            print('  %-46s %3d -> %3d sections' % ('/'.join(here), len(had), len(want)))
            node['sections'] = [{'ref': r} for r in want]

    if '--write' in sys.argv:
        for path, doc in docs.items():
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(json.dumps(doc, indent=4, ensure_ascii=False) + '\n')
        print('%d area pins rewritten, %+d sections' % (changed, grew))
    else:
        print('%d area pins would change, %+d sections  (--write to apply)'
              % (changed, grew))


if __name__ == '__main__':
    main()

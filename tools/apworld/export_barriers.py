"""Add the barrier, box and search checks to locations/ and location_mapping.lua.

Each is one destructible object in one room, so they group per region and per
room the way chests already do.

The flag tables name the room a check sits in ("MAP_DUNG_A01.rf4m"), and
tools/generated/room_pins.json says where that room is drawn, so the two join on the map
id directly.

A room listed there gets its own pin on its own map. A room that is not -- one
the game never draws -- gets a section on the region's aggregate pin, parked
with the shipment and tame pins rather than pretending to a position it does
not have. It is promoted by rooms.json gaining that map id, and the check ids
and the tree stay as they are.

Regions that have no map of their own fold into the one that hosts them.
"""
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, HERE)
import load                                          # noqa: E402
from load import apworld                            # noqa: E402

AP = apworld()
L = AP.Locations

OURS = re.compile(r'/Rm\d+(\.\d+)?"\}')   # only this script writes RmN sections
# Which kinds are map objects is discovered, not listed: a kind the apworld
# adds shows up here on its own, with its name as the label.
KINDS = load.map_kinds(AP)
CLOSED, OPENED = '/images/items/close.png', '/images/items/open.png'


def map_ids():
    """(region, room number) -> map id, from the apworld's own flag tables."""
    out = {}
    for name in ('%s_flags' % k for k in KINDS):
        for e in AP.data(name):
            out[(e['region'], e['room_number'])] = \
                re.sub(r'\.rf4m$', '', e['map_name'])
    return out


def load_meta():
    """apid -> (region, room number, map id, kind)"""
    where = map_ids()
    rooms = {}
    real = {d.address for d in L.location_data_table.values()
            if d.loc_type in KINDS and d.address is not None}
    for kind in KINDS:
        tbl = getattr(L, kind + '_data_table')
        for _, d in tbl.items():
            if d.apid in real:
                rooms[d.apid] = (d.region, d.room_number,
                                 where.get((d.region, d.room_number)), kind)
    return rooms


def child(node, name):
    for c in node.get('children', []) or []:
        if c.get('name') == name:
            return c
    return None


def parent_region():
    """{region: the region that leads into it}, from the apworld's own graph."""
    out = {}
    for name, data in AP.Regions.region_data_table.items():
        for child in (data.connecting_regions or []):
            out.setdefault(child, name)
    return out


def owning_file():
    """{pack map: the locations file that owns it}.

    A map is owned by the file whose aggregate or chest pins sit on it, which is
    the game's answer once those are placed from the map files. Where two files
    both pin on one map the majority wins, and both cases are a check filed
    under one region while drawn on another's map. Read from pins this script
    does not write, so it cannot feed on its own output.
    """
    anchor = collections.defaultdict(collections.Counter)
    for path in sorted(glob.glob(PACK + 'locations/*.json')):
        fname = os.path.basename(path)[:-len('.json')]

        def walk(nodes, trail):
            for nd in nodes:
                here = trail + [str(nd.get('name') or '')]
                if not generated(nd) and (here[-1] in ('Shipment', 'Tame')
                                          or 'Chest' in here):
                    for m in (nd.get('map_locations') or []):
                        anchor[m['map']][fname] += 1
                walk(nd.get('children') or [], here)

        walk(json.load(open(path, encoding='utf-8')), [])
    return {m: c.most_common(1)[0][0] for m, c in anchor.items()}


def pins():
    """map id -> where its pin goes, or {} if derive_rooms has not run."""
    path = PACK + 'tools/generated/room_pins.json'
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def generated(node):
    """Did a previous run make this node? They are rebuilt from scratch, so a
    room that gains a pin stops being a section on the aggregate.

    Matched on the section names rather than the node's, because the pack has
    real checks called things like "Light Barrier" and "Broken Box" that a name
    test would sweep up. Only this script writes sections called Rm4 or Rm4.2.
    """
    secs = node.get('sections') or []
    return bool(secs) and all(re.fullmatch(r'Rm\d+(\.\d+)?', s.get('name', ''))
                              for s in secs)


def main():
    meta = load_meta()
    pin_room = pins()
    owner = owning_file()

    groups = collections.defaultdict(list)
    for apid, (region, room, map_id, kind) in sorted(meta.items()):
        groups[(region, kind)].append((apid, room, map_id))

    def home(entries):
        """(locations file, map to park an aggregate on) for one group.

        Both come from where the game draws the group's rooms, so a region files
        with the map it is drawn on rather than with the one its name suggests.
        """
        drawn = collections.Counter(pin_room[m]['map'] for _, _, m in entries
                                    if m and m in pin_room)
        if not drawn:
            return None, None
        top = drawn.most_common(1)[0][0]
        return owner.get(top, top), top

    # A region the game draws no minimap for -- Forest Of Beginnings -- has no
    # map to be filed by, so it follows the region that leads into it.
    parent = parent_region()
    drawn_home = {}
    for (region, kind), entries in groups.items():
        drawn_home.setdefault(region, home(entries))
    for region in list(drawn_home):
        seen, at = {region}, region
        while drawn_home.get(at, (None, None))[0] is None:
            at = parent.get(at)
            if at is None or at in seen:
                break
            seen.add(at)
        if at and drawn_home.get(at, (None, None))[0]:
            drawn_home[region] = drawn_home[at]

    by_file = collections.defaultdict(lambda: collections.defaultdict(list))
    park = {}
    for key, entries in groups.items():
        fname, on_map = drawn_home.get(key[0], (None, None))
        by_file[fname or key[0]][key] = entries
        park[key] = on_map

    mapping = {}
    placed_n = 0
    for fname, groups in sorted(by_file.items()):
        path = PACK + 'locations/%s.json' % fname
        if not os.path.exists(path):
            raise SystemExit('no locations file for %r' % fname)
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
        root = doc[0] if isinstance(doc, list) else doc
        root.setdefault('children', [])
        # drop what a previous run made BEFORE looking at which rows are
        # taken, or the aggregate pins walk down the map a little each run
        root['children'] = [c for c in root['children'] if not generated(c)]
        # park the aggregate pins under the ones already there
        used_y = set()
        for c in root['children']:
            for ml in c.get('map_locations', []) or []:
                used_y.add(ml.get('y'))
        for (region, kind), entries in sorted(groups.items()):
            label, closed, opened = kind.title(), CLOSED, OPENED
            shared = region != fname
            per_room = collections.defaultdict(list)
            loose = collections.defaultdict(list)
            spot_for = {}
            for apid, room, map_id in sorted(entries, key=lambda e: (e[1], e[0])):
                spot = pin_room.get(map_id) if map_id else None
                if spot:
                    spot_for[room] = spot
                    per_room[room].append(apid)
                else:
                    loose[room].append(apid)

            def node_for(name, where):
                node = {'name': name,
                        'chest_unopened_img': closed, 'chest_opened_img': opened,
                        'overlay_background': '#000000',
                        'access_rules': [' '], 'sections': [],
                        'map_locations': [where]}
                root['children'].append(node)
                return node

            def add(node, room, apids):
                names = set()
                for i, apid in enumerate(apids, 1):
                    sec = 'Rm%d' % room if len(apids) == 1 else 'Rm%d.%d' % (room, i)
                    assert sec not in names, (node['name'], sec)
                    names.add(sec)
                    node['sections'].append({
                        'name': sec,
                        'access_rules': ['^$RF4Access|%d' % apid],
                        'visibility_rules': ['opt_%ssanity,$RF4Visible|%d'
                                             % (kind, apid)],
                        'item_count': 1})
                    mapping[apid] = '@%s/%s/%s' % (root['name'], node['name'], sec)

            # A label is only unique within one map, so where a region spans
            # several -- Rune Prana's floors, the Floating Empire's wings -- the
            # map has to be part of the name or two rooms collide on one node.
            per_label = collections.Counter(
                spot_for[r]['label'] for r in per_room)
            for room in sorted(per_room):
                placed_n += len(per_room[room])
                spot = spot_for[room]
                name = '%s %s' % (label, spot['label'])
                if per_label[spot['label']] > 1:
                    floor = spot['map'][len(region):].strip() or spot['map']
                    name = '%s %s:%s' % (label, floor, spot['label'])
                if shared:
                    name = '%s %s' % (region, name)
                add(node_for(name, {'map': spot['map'], 'x': spot['x'],
                                    'y': spot['y'], 'size': 6}),
                    room, per_room[room])

            if loose:
                name = label if not shared else '%s %s' % (region, label)
                y = 34
                while y in used_y:
                    y += 22
                used_y.add(y)
                node = node_for(name, {'map': park[(region, kind)], 'x': 34, 'y': y,
                                       'size': 6, 'shape': 'trapezoid'})
                for room in sorted(loose):
                    add(node, room, loose[room])
        # Two nodes of one name under the same root are ambiguous to
        # PopTracker: it resolves the first, and the second one's sections
        # become unreachable.
        names = collections.Counter(c.get('name') for c in root['children'])
        dupes = [n for n, c in names.items() if c > 1]
        if dupes:
            raise SystemExit('%s: %d duplicated node names, e.g. %s'
                             % (fname, len(dupes), dupes[:4]))
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(doc, fh, indent=4, ensure_ascii=False)
            fh.write('\n')

    # merge into location_mapping.lua
    mapping_path = PACK + 'scripts/autotracking/location_mapping.lua'
    body = open(mapping_path, encoding='utf-8').read()
    have = set(int(m) for m in re.findall(r'^\s*\[(\d+)\]', body, re.M))
    added = [i for i in sorted(mapping) if i not in have]
    # A room that gains a pin moves to a new path, so rewrite rather than skip.
    # An id this script no longer emits is dropped, which is how the ids that
    # upstream split into one per flag stop pointing at a section that is gone;
    # only lines naming an RmN section are ours to drop.
    dropped = []

    def redirect(m):
        i, line = int(m.group(1)), m.group(0)
        if i in mapping:
            return '\t[%d] = {"%s"},' % (i, mapping[i].replace('"', '\\"'))
        if OURS.search(line):
            dropped.append(i)
            return None
        return line

    out = []
    for line in body.splitlines(True):
        m = re.match(r'^\t\[(\d+)\] = \{.*?\},$', line.rstrip('\n'))
        if not m:
            out.append(line)
            continue
        new = redirect(m)
        if new is not None:
            out.append(new + '\n')
    body = ''.join(out)
    lines = ''.join('\t[%d] = {"%s"},\n' % (i, mapping[i].replace('"', '\\"'))
                    for i in added)
    body = body.rstrip()
    assert body.endswith('}')
    body = body[:-1] + lines + '}\n'
    open(mapping_path, 'w', encoding='utf-8', newline='\n').write(body)
    # invariants worth failing on rather than shipping: two sections of one
    # name in a node are ambiguous to PopTracker, and two checks on one path
    # means a check that can never be marked
    used = collections.Counter(mapping.values())
    clash = [path for path, n in used.items() if n > 1]
    if clash:
        raise SystemExit('%d paths used by more than one check: %s'
                         % (len(clash), clash[:3]))
    if dropped:
        print('  ids no longer AP  %4d  (dropped from the mapping)' % len(dropped))
    print('map-object checks   %4d' % len(meta))
    print('  on their own pin   %4d' % placed_n)
    print('  on an aggregate    %4d' % (len(meta) - placed_n))
    print('location files       %4d' % len(by_file))
    print('mapping entries new  %4d' % len(added))


if __name__ == '__main__':
    main()

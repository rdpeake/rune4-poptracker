"""Move the pins in locations/*.json onto the game's own room positions.

The room labels come from `rf3MapMiniPos.bin` now (see derive_rooms.py), so the
pins have to follow or a check ends up beside the room it names. Three ways to
tell which room a pin belongs to, in order:

  by object  a chest, barrier or box IS an object in a room of the map files,
             and generated/check_rooms.json says which. This is the game's own
             answer and beats the name, which is hand-entered upstream and
             disagrees for 26 of the 181 chests.
  by name    the rest mostly carry the room code -- "Barrier D4", "Box F2:J1".
             Take the code, look it up in that map's rooms.
  by nearest what is left (area transitions, unnamed spurs) keeps no code, so it
             takes whichever room it sits closest to.

A check placed by object gets one pin per room it is in, so a node holding two
chests in different rooms is drawn in both. tools/pin_remap.json adds rooms by
hand for the few whose real room is somewhere a player would not look, or is not
drawn at all; those keep the game's pin and gain the named one.

Where a pin ends up depends only on its room and on how many pins share that
room, never on where the pin happens to be now, so running this twice moves
nothing the second time.

Pins parked off-map in the x=34 column are aggregates and never move.

    python3 tools/move_pins.py            report
    python3 tools/move_pins.py --write    apply
"""
import collections
import glob
import json
import os
import re
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
PARKED_X = 34
NEAR = 60           # a pin further than this from any room is left alone

# A pin sits on the room's own point, which is where the label is drawn too, so
# the marker covers the text. Lift it clear, and fan pins that share a room.
LIFT = 9            # above the label: half the cap height, half the marker, a gap
FAN = 10            # between two pins in the same room
EDGE = 5            # keep a marker this far inside the room's box


def aliases(maps):
    """old room code -> current one, per map image"""
    raw = json.load(open(PACK + 'tools/room_code_aliases.json'))
    return {maps[k]: v for k, v in raw.items() if not k.startswith('_') and k in maps}


def by_img(path, maps):
    """{map image: {room code: value}} out of a {map name: {...}} file"""
    out = {}
    for name, rs in json.load(open(PACK + path)).items():
        img = maps.get(name)
        if img:
            out.setdefault(img, {}).update(rs)
    return out


def place(centre, size, i, n):
    """where the i-th of n pins in a room goes: lifted off the label, fanned"""
    cx, cy = centre
    w, h = size or (0, 0)
    dy = -min(LIFT, max(0, h // 2 - EDGE)) if h else -LIFT
    # fan at FAN apart, closing up if that would not fit inside the room
    wanted = (n - 1) * FAN
    usable = max(0, w // 2 - EDGE) * 2 if w else wanted
    step = FAN if wanted <= usable else (usable / (n - 1) if n > 1 else 0)
    dx = round((i - (n - 1) / 2) * step)
    return [cx + dx, cy + dy]


def rooms_by_img():
    """(room positions by image, map name -> image)"""
    maps = {m['name']: m['img'].replace('images/maps/', '')
            for m in json.load(open(PACK + 'maps/maps.json'))}
    return by_img('tools/generated/room_positions.json', maps), maps


def drawn_on(docs):
    """section path -> the maps the pin holding it sits on"""
    out = collections.defaultdict(set)

    def walk(nodes, trail):
        for x in nodes:
            here = trail + [str(x.get('name') or '')]
            on = [mp['map'] for mp in x.get('map_locations') or []]
            for sec in x.get('sections') or []:
                if 'ref' not in sec:
                    out['/'.join(here + [str(sec.get('name') or '')])].update(on)
            walk(x.get('children') or [], here)

    for doc in docs.values():
        walk(doc, [])
    return out


def by_door(docs, maps):
    """{node path: [(map name, img, code)]} for the pins that mark a way in.

    Such a pin is a node whose sections are all refs: it stands for somewhere
    else, and shows how much of it is left. Where that somewhere is drawn comes
    from the refs themselves, and the game's own map files say which room you
    leave from to get there -- generated/transitions.json is every doorway whose
    two ends are drawn on different maps, and tools/pin_doors.json is the handful
    it has no doorway for.
    """
    path = PACK + 'tools/generated/transitions.json'
    if not os.path.exists(path):
        return {}
    doors = json.load(open(path, encoding='utf-8'))
    # a way in the map files have no doorway for -- Revival Cave is a pit
    for src, v in json.load(open(PACK + 'tools/pin_doors.json',
                                 encoding='utf-8')).items():
        if not src.startswith('_'):
            doors.setdefault(src, {}).update(v)
    where = drawn_on(docs)
    out = {}

    def walk(nodes, trail):
        for x in nodes:
            here = trail + [str(x.get('name') or '')]
            secs = x.get('sections') or []
            on = [mp['map'] for mp in x.get('map_locations') or []]
            if secs and on and on[0] in doors and all('ref' in s for s in secs):
                lead = set()
                for sec in secs:
                    lead |= where.get(sec['ref'], set())
                img = maps.get(on[0])
                for to in sorted(lead - {on[0]}):
                    for code in doors[on[0]].get(to, ()):
                        if img:
                            out.setdefault('/'.join(here), []).append(
                                (on[0], img, code))
            walk(x.get('children') or [], here)

    for doc in docs.values():
        walk(doc, [])
    return {k: sorted(set(v)) for k, v in out.items()}


def by_object(maps):
    """{node path: [(map name, img, code)]} for checks the map files place."""
    rooms = json.load(open(PACK + 'tools/generated/room_pins.json',
                           encoding='utf-8'))
    where = json.load(open(PACK + 'tools/generated/check_rooms.json',
                           encoding='utf-8'))
    remap = json.load(open(PACK + 'tools/pin_remap.json', encoding='utf-8'))
    text = open(PACK + 'scripts/autotracking/location_mapping.lua',
                encoding='utf-8').read()

    out = {}
    for apid, path in re.findall(r'\[(\d+)\]\s*=\s*\{"([^"]+)"', text):
        node = '/'.join(path.lstrip('@').split('/')[:-1])
        extra = remap.get(apid, {}).get('rooms', []) if apid != '_' else []
        for map_id in list(where.get(apid, ())) + list(extra):
            r = rooms.get(map_id)
            img = maps.get(r['map']) if r else None
            if img:
                out.setdefault(node, []).append((r['map'], img, r['label']))
    return {k: sorted(set(v)) for k, v in out.items()}


def code_in(name):
    """the room code a location's name carries, if any"""
    if not name:
        return None
    m = re.search(r'\b([A-Z]\d{0,2}(?:-\d+)?)\s*$', name.strip())
    if m:
        return m.group(1)
    m = re.search(r':\s*([A-Za-z0-9?-]+)\s*$', name.strip())
    return m.group(1) if m else None


def main():
    derived, maps = rooms_by_img()
    alias = aliases(maps)
    extents = by_img('tools/generated/room_extents.json', maps)
    docs, want = {}, {}          # (file, id) -> map_location ; and its room
    order = []
    parked = kept = named = nearest = objects = added = 0

    for path in sorted(glob.glob(PACK + 'locations/*.json')):
        docs[path] = json.load(open(path, encoding='utf-8'))

    # an object's own room beats a doorway, which beats the name on the node
    placed = dict(by_door(docs, maps))
    placed.update(by_object(maps))

    for path, doc in docs.items():

        def walk(nodes, trail):
            nonlocal parked, kept, named, nearest, objects, added
            for x in nodes:
                here = trail + [str(x.get('name') or '')]
                spots = placed.get('/'.join(here))
                if spots and (x.get('map_locations') or []):
                    # Each room keeps its own pin across runs: spots is sorted,
                    # so slot i is the same room every time and only a room
                    # gaining its first pin clones one.
                    was = x['map_locations']
                    fresh = []
                    for i, (name, img, code) in enumerate(spots):
                        mp = dict(was[i] if i < len(was) else was[0], map=name)
                        fresh.append(mp)
                        key = (path, id(mp))
                        want[key] = (img, code)
                        order.append((key, mp, '/'.join(here[1:])))
                    added += len(fresh) - len(x['map_locations'])
                    objects += len(fresh)
                    x['map_locations'] = fresh
                    walk(x.get('children') or [], here)
                    continue
                for mp in x.get('map_locations') or []:
                    img = maps.get(mp['map'])
                    if not img or img not in derived:
                        kept += 1
                        continue
                    if mp['x'] == PARKED_X:
                        parked += 1
                        continue
                    code = None
                    for part in reversed(here):
                        c = code_in(part)
                        c = alias.get(img, {}).get(c, c)
                        if c and c in derived[img]:
                            code, how = c, 'name'
                            break
                    if code is None:
                        # Measured against the room positions this tool places
                        # onto, not the pin's current spot, so a pin it has
                        # already lifted still matches its own room and running
                        # again is a no-op.
                        near = [(((mp['x'] - v[0]) ** 2 + (mp['y'] - v[1]) ** 2) ** 0.5, c)
                                for c, v in derived[img].items()]
                        if near:
                            d, c = min(near)
                            if d <= NEAR:
                                code, how = c, 'nearest'
                    if code is None:
                        kept += 1
                        continue
                    named += how == 'name'
                    nearest += how == 'nearest'
                    key = (path, id(mp))
                    want[key] = (img, code)
                    order.append((key, mp, '/'.join(here[1:])))
                walk(x.get('children') or [], here)

        walk(doc, [])

    rooms = {}
    for key, mp, label in order:
        rooms.setdefault(want[key], []).append((key, mp, label))

    moved, changes = 0, []
    for (img, code), group in rooms.items():
        n = len(group)
        for i, (key, mp, label) in enumerate(sorted(group, key=lambda g: g[2])):
            dest = place(derived[img][code], (extents.get(img) or {}).get(code), i, n)
            if [mp['x'], mp['y']] != dest:
                changes.append((os.path.basename(key[0]), label, (mp['x'], mp['y']),
                                tuple(dest), code, n))
                mp['x'], mp['y'] = dest
                moved += 1

    print('%d pins placed  (%d by object, %d by name, %d by nearest room)'
          % (moved, objects, named, nearest))
    print('%d rooms hold more than one pin; %d parked, %d left alone'
          % (sum(1 for g in rooms.values() if len(g) > 1), parked, kept))
    if added:
        print('%+d pins on checks the game puts in more than one room' % added)
    if '--write' in sys.argv:
        for path, doc in docs.items():
            raw = open(path, encoding='utf-8', newline='').read()
            out = json.dumps(doc, indent=4, ensure_ascii=False) + ('\n' if raw.endswith('\n') else '')
            if out != raw:
                open(path, 'w', encoding='utf-8', newline='').write(out)
        print('written')
    elif changes:
        print('\nsample:')
        for c in changes[:8]:
            print('   %-24s %-30s %s -> %s  (%s, %d in room)'
                  % (c[0][:-5], c[1][:30], c[2], c[3], c[4], c[5]))


if __name__ == '__main__':
    main()

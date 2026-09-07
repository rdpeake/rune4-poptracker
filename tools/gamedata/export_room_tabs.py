"""Export the game's room-id table into a PopTracker tab mapping.

The RF4 client reports which room the player is standing in, and
Tracker:UiHint("ActivateTab", <name>) switches tabs from Lua, so a room id plus
a path of tab names is enough to follow the player across the maps. The path is
sent outermost first, since every tabbed container receives the hint and applies
it only if it holds a tab of that name.

Which tab a room belongs to is not written down here. It falls out of the same
data the map images are drawn from:

    map id -> minimap sheet   rf3MapMiniPos.bin, the game's own table
    sheet  -> pack image      tools/map_art.json, which textures draw what
    image  -> map name        maps/maps.json
    name   -> tab path        the map widgets in layouts/*.json

That chain is exact where the old hand-written tables were inferred, and it
knows the floor as well as the area, so a room in Rune Prana F3 opens F3 rather
than stopping at the floor picker. It agrees with the room-to-map assignment
already used to place the barrier and box pins on all 651 rooms both cover.

Two kinds of room fall outside it. One whose sheet no pack image draws is an
interior -- the pack has no map for the inside of a house, so entering one holds
whatever map was showing. One the game leaves on the blank sheet cannot be
placed at all; BLANK_SHEET below names the few areas that need saying by hand,
and it is the only hand-written mapping left.

What the table says is taken at face value otherwise. Rooms that look
surprising -- a few Yokmir Forest and Water Ruins ids, and the Obsidian Mansion
rooms past the end of its map -- all report Selphia, and none of them is reached
from anywhere in the map files, so the town is as good an answer as the game
gives. Second-guessing them on whether they carry a fog box does not work: the
town has nothing to reveal, so no room on its sheet carries one and none ever
could.

The mansion's own way into Selphia is not among them -- that is MAP_CITY_04 to
MAP_DUNG_C02, an ordinary doorway on the mansion's own map.

    python3 tools/gamedata/export_room_tabs.py
    python3 tools/gamedata/export_room_tabs.py --report   what is still unplaced
"""
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import PACK                             # noqa: E402
sys.path.insert(0, PACK + 'tools')
from read_minipos import sheets                    # noqa: E402
from room_ids import room_names                    # noqa: E402

SEASON = re.compile(r'_(SUMMER|AUTUMN|WINTER)$')

# Areas the game draws on the blank sheet, so the minimap table cannot place
# them, but which the pack has a map for anyway. Keyed by the dungeon letter or
# the map-name prefix, and matched against the pack map they belong on.
BLANK_SHEET = {
    'MAP_DUNG_I': 'Forest of Beginnings',   # no minimap in game at all
    'MAP_DUNG_F': 'Sharance Maze',          # entered from the Sharance Tree
    'MAP_FARM':   'Selphia',                # its own sheet, which no map draws
}

def tab_paths():
    """{pack map name: the tab path that shows it}, from the layouts.

    A layout's map widget names the maps it draws, so the nesting above it is
    the path ActivateTab has to walk. Read rather than repeated here: a tab
    renamed in the layout would otherwise leave this pointing at nothing.
    """
    found = collections.defaultdict(set)

    def walk(node, path):
        if isinstance(node, dict):
            if node.get('type') == 'tabbed':
                for tab in node.get('tabs', []):
                    walk(tab, path + [tab.get('title')])
            for key, value in node.items():
                if key != 'tabs':
                    walk(value, path)
            for name in node.get('maps') or ([node['map']] if 'map' in node else []):
                found[name].add(tuple(p for p in path if p))
        elif isinstance(node, list):
            for value in node:
                walk(value, path)

    for path in sorted(glob.glob(PACK + 'layouts/*.json')):
        with open(path, encoding='utf-8') as fh:
            walk(json.load(fh), [])
    # a map shown in two places has no single path to activate
    return {name: min(paths, key=len) for name, paths in found.items()}


def image_of_sheet():
    """{minimap sheet: the pack image that draws it}.

    Where a sheet is drawn twice the bigger drawing wins, which puts a room on
    its own map rather than its corner of the Overworld composite. A pack image
    may name a texture variant (`..._1`) of the sheet a room reports, so the
    trailing number is dropped when it does not match outright.
    """
    on_sheet = sheets()
    known = set(on_sheet.values())
    best = {}
    art = json.load(open(PACK + 'tools/map_art.json', encoding='utf-8'))
    for img, cfg in art.items():
        for piece in cfg['art']:
            tex = piece['tex']
            if tex not in known:
                tex = re.sub(r'_\d+$', '', tex)
            area = piece['w'] * piece['h']
            if tex not in best or area > best[tex][0]:
                best[tex] = (area, img)
    # mini_map_rnd_* are the Sharance Maze's randomised floor templates. The
    # pack pins them to its Sharance Maze image, but the game hands the same
    # tiles to a few rooms elsewhere, so a room on one says nothing about which
    # area it is in. BLANK_SHEET places the maze itself.
    return {tex: img for tex, (_, img) in best.items() if '_rnd_' not in tex}


def main():
    room_name = {i: SEASON.sub('', n) for i, n in room_names().items()}
    names = {m['img'].replace('images/maps/', ''): m['name']
             for m in json.load(open(PACK + 'maps/maps.json', encoding='utf-8'))}
    paths = tab_paths()
    image = image_of_sheet()
    on_sheet = sheets()
    # read() keys its rooms by resource name, not by id

    mapped, held = {}, set()
    for room_id, name in room_name.items():
        by_hand = next((m for prefix, m in BLANK_SHEET.items()
                        if name.startswith(prefix)), None)
        sheet = on_sheet.get(room_id)
        img = image.get(sheet) if sheet else None
        path = paths.get(names.get(img)) if img else None
        if path:
            mapped[room_id] = path
        elif by_hand and by_hand in paths:
            mapped[room_id] = paths[by_hand]
        elif sheet is not None:
            held.add(room_id)          # a sheet no pack map draws: an interior

    out = PACK + 'scripts/autotracking/tab_mapping.lua'
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write("-- GENERATED by tools/gamedata/export_room_tabs.py from"
                " tools/room_ids.json,\n")
        f.write("-- the game's minimap table, tools/map_art.json and the"
                " layouts. Do not edit.\n")
        f.write("--\n")
        f.write("-- RF4_ROOM_NAME   room id -> resource name, season suffix stripped\n")
        f.write("-- RF4_TAB_MAPPING room id -> tab path, outer to inner\n")
        f.write("-- RF4_ROOM_HOLD   rooms with no map of their own; entering one\n")
        f.write("--                 leaves the map where it was\n")

        f.write("\nRF4_ROOM_NAME = {\n")
        for i in sorted(room_name):
            f.write('    [%d] = "%s",\n' % (i, room_name[i]))
        f.write("}\n")

        f.write("\nRF4_TAB_MAPPING = {\n")
        for i in sorted(mapped):
            f.write('    [%d] = {%s},   -- %s\n'
                    % (i, ", ".join('"%s"' % t for t in mapped[i]), room_name[i]))
        f.write("}\n")

        f.write("\nRF4_ROOM_HOLD = {\n")
        for i in sorted(held):
            f.write('    [%d] = true,   -- %s\n' % (i, room_name[i]))
        f.write("}\n")

    print("wrote %s" % out)
    print("  rooms            %5d" % len(room_name))
    print("  with a tab path  %5d" % len(mapped))
    print("  interiors held   %5d" % len(held))
    print("  unplaced         %5d" % (len(room_name) - len(mapped) - len(held)))

    if '--report' in sys.argv:
        rest = collections.Counter(
            re.sub(r'\d+$', '', room_name[i]) for i in room_name
            if i not in mapped and i not in held)
        print("\nstill unplaced, by group:")
        for group, count in rest.most_common():
            print("  %-24s %4d" % (group, count))


if __name__ == '__main__':
    main()

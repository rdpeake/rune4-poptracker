"""Work out which grid sheet each shipment belongs on, and in what order.

The sheets used to be the apworld's REGIONS, which is where a check is gated,
not where it comes from: `Fur (L)` is what a tamed Wooly gives you, and it sat
on the Selphia sheet because Floating Empire is what unlocks it. 266 of the 492
were filed that way.

So a sheet is what the item IS, from the Shipments sheet's own `Type` column,
and a band inside it says which kind. Ordering is the `Tier` column, which is
the same number the max-shipment-tier setting cuts on, and it comes out as a
ruler under the tiles saying where each tier run starts and ends.

Three kinds get their own treatment:

    drops and collectables   the region really is where you find them, so the
                             band is the overworld region you go through and
                             the ruler names the area. Autumn Road holds half of
                             them, so it gets a sheet of its own where the areas
                             head their own bands.
    crops and seeds          a seed, the crop it grows and that crop's large
                             form sit together: the game numbers a crop and its
                             large form N and N+1, and all three carry one tier,
                             so the pairing and the tier order agree.
    barn products            Egg, Milk, Fur and Honey are what a tamed monster
                             gives you, so they band by the monster.

The tame sheets were the last family filed by the doorway: five sheets named for
the overworld hub you reach a place through, so Rune Prana's 32 tames sat under
a tab called Autumn Road and that one sheet held 86 of the 149. They are six
sheets now, each named for an area ON it and holding the areas you walk in the
same stretch of the run, with the area as the band and the tier as the ruler.
An area is never split across two sheets: cutting strictly on tier balances the
sheets better and lands the max-shipment-tier cut on a tab boundary, but it
shreds a dungeon across tabs -- one trial sheet came out eleven bands for 35
tiles, six of them one tile tall.

What tames a monster is not read from the Tame CSV at all: the game lists up to
four gifts where the CSV keeps one, so `gamedata/export_monster_presents.py`
takes them from the game's own tables into `generated/tame_gifts.json`, which
`export_grid_maps.py` badges onto the tile and `export_tame_gifts.py` names on
the pin.

The crafted sheets were already grouped by how you make a thing, so they only
gain bands: one per Subtype, ordered by the crafting Level, with the ruler
bracketing level decades because a recipe has no tier and its level is
near-unique. Forge and Cooking are split in two so a sheet fits its pane
without shrinking the tiles to read them -- Forge on the same boundary the item
panel's weapon tabs already use.

Writes tools/generated/grid_layout.json: sheet -> the pins on it, in order.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, HERE)
from load import apworld, csv_rows, map_kinds             # noqa: E402

AP = apworld()
OUT = PACK + 'tools/generated/grid_layout.json'

SHEET = {
    'Drop': 'Drops', 'Boss': 'Drops', 'Mineral': 'Drops', 'Grass': 'Drops',
    'Mushroom': 'Drops',
    'Fish': 'Fish',
    'Crop': 'Crops & Seeds', 'Seed': 'Crops & Seeds', 'Fruit': 'Crops & Seeds',
    'Large Crop': 'Crops & Seeds', 'Gold Crop': 'Crops & Seeds',
    'Spell': 'Spells',
    'Potion': 'Food & Medicine', 'Grocery': 'Food & Medicine',
    'Bread': 'Food & Medicine', 'Vitamin': 'Food & Medicine',
    'Ingredient': 'Barn Products', 'Product': 'Barn Products',
    'Tool': 'Other', 'Forge': 'Other', 'Special': 'Other', 'Other': 'Other',
}
BY_PLACE = ('Drops', 'Fish')          # sheets banded by where you find things
OWN_SHEET = 'Autumn Road'             # the region big enough to want one
HUBS = ('Selphia', 'Selphia Plains', 'Autumn Road', 'Sercerezo Hill')
# areas the game's doorways do not reach: the airship, the two event dungeons
# and a pit you fall down
BY_HAND = {'Floating Empire': 'Selphia', 'Sharance Maze': 'Selphia',
           'Field Dungeon': 'Selphia', 'Revival Cave': 'Autumn Road',
           'Anywhere (Rare)': 'Anywhere'}
# Shade Stone's Region column holds its Type, so upstream gives it no place
REGION_FIX = {'Shade Stone': 'Selphia Plains - West'}
# seeds the "<crop> Seeds" rule does not reach
SEED_CROP = {
    'Clover Seeds': '4-Leaf Clover', 'Moondrop Seeds': 'Moondrop Flower',
    'Hot-Hot Seeds': 'Hot-Hot Fruit', 'Pom-Pom Grass Sds.': 'Pom-Pom Grass',
    'Sword Seed': 'Plant Sword', 'Shield Seed': 'Magic Plant Shield',
    'Gold Cabbage Seeds': 'Golden Cabbage', 'Gold Potato Seeds': 'Golden Potato',
    'Gold Pumpkin Seeds': 'Golden Pumpkin', 'Gold Turnip Seeds': 'Golden Turnip',
    'Apple Tree Seeds': 'Apple', 'Grape Tree Seed': 'Grapes',
    'Orange Tree Seed': 'Orange',
}


# The tame sheets, in the order you walk them. An area sits on exactly one, and
# a sheet is named for an area it holds rather than for the hub that gates it.
TAME_SHEETS = (
    ('Selphia Plains', ('Selphia Plains', 'Water Ruins', 'Yokmir Forest',
                        'Cluck Cluck Nest', 'Anywhere (Rare)')),
    ('Autumn Road', ('Obsidian Mansion', 'Autumn Road', 'Delirium Lava Ruins',
                     'Maya Road')),
    ('Sercerezo Hill', ('Sercerezo Hill', 'Field Dungeon', 'Idra Cave',
                        'Demons Den')),
    ('Sechs Territory', ('Sechs Territory', 'Leon Karnak')),
    ('Floating Empire', ('Floating Empire', 'Sharance Maze')),
    ('Rune Prana', ('Rune Prana',)),
)


def rows(sheet):
    return csv_rows(sheet, strip_slashes=True, by_name=True)


SHIP = rows('Shipments')
REC = rows('Recipes')
TAME = rows('Tame')
# the item panel splits its weapon tabs here, so the sheets match it
FORGE_I = ('Short Sword', 'Long Sword', 'Dual Blade', 'Spear')
COOK_I = ('Frying Pan', 'Pot', 'Knife')


def num(s):
    s = (s or '').strip()
    return int(s) if s.isdigit() else None


def gid(row):
    try:
        return int(row['ID'], 16)
    except Exception:
        return 1 << 30


def hub_of():
    """pack area -> the overworld region you reach it from, per the map files"""
    tr = json.load(open(PACK + 'tools/generated/transitions.json', encoding='utf-8'))
    adj = collections.defaultdict(set)
    for a, v in tr.items():
        for b in v:
            adj[a].add(b)
            adj[b].add(a)
    owner = {h: h for h in HUBS}
    q = collections.deque(HUBS)
    while q:
        a = q.popleft()
        for b in sorted(adj[a]):
            if b not in owner:
                owner[b] = owner[a]
                q.append(b)

    # A region is not always drawn on the map its name suggests -- Selphia
    # Plains - West is drawn on Autumn Road -- and the apworld's flag tables say
    # which map each region's rooms are in, so ask them first.
    pins = json.load(open(PACK + 'tools/generated/room_pins.json', encoding='utf-8'))
    drawn = collections.defaultdict(collections.Counter)
    # map_kinds asks the apworld which loc_types are objects placed in a room,
    # so a kind it adds is picked up here rather than named by hand
    for kind in map_kinds(AP):
        try:
            flags = AP.data('%s_flags' % kind)
        except Exception:
            continue
        for e in flags:
            r = pins.get(re.sub(r'\.rf4m$', '', e['map_name']))
            if r:
                drawn[e['region']][r['map']] += 1
    home = {k: v.most_common(1)[0][0] for k, v in drawn.items()}

    def of(area, region=None):
        # the region's own map wins, but only if the doorways reached it: Rune
        # Prana F7 and the airship are drawn on maps nothing walks into
        if home.get(region) in owner:
            return owner[home[region]]
        if area in BY_HAND:
            return BY_HAND[area]
        for m, h in owner.items():                 # "Rune Prana" -> "Rune Prana F1"
            if m == area or m.startswith(area + ' '):
                return h
        return 'Anywhere'
    return of


def crop_order():
    """crop -> (tier, game id), and seed -> the crop it grows"""
    crops = {nm: (num(r.get('Tier')), gid(r)) for nm, r in SHIP.items()
             if (r.get('Type') or '').strip() in
             ('Crop', 'Large Crop', 'Gold Crop', 'Fruit')}
    seed_of = {}
    for nm, r in SHIP.items():
        if (r.get('Type') or '').strip() != 'Seed':
            continue
        base = SEED_CROP.get(nm)
        if not base:
            for suffix in (' Seeds', ' Seed'):
                if nm.endswith(suffix):
                    base = nm[:-len(suffix)]
                    break
        seed_of[nm] = base if base in crops else None
    return crops, seed_of


def refs(src):
    doc = json.load(open(PACK + 'locations/' + src, encoding='utf-8'))
    root = doc[0] if isinstance(doc, list) else doc
    for n in (root.get('children') or []):
        r = (n.get('sections') or [{}])[0].get('ref')
        if r:
            yield r, (n.get('map_locations') or [{}])[0].get('map')


def crafted(out):
    """one band per Subtype, ordered by crafting level"""
    for path, sheet in refs('_Crafting.json'):
        nm = path.rsplit('/', 1)[-1]
        r = REC.get(nm)
        band = (r.get('Subtype') or 'Other').strip() if r else 'Other'
        lv = num(r.get('Level')) if r else None
        if sheet == 'Forge':
            sheet = 'Forge I' if band in FORGE_I else 'Forge II'
        elif sheet == 'Cooking':
            sheet = 'Cooking I' if band in COOK_I else 'Cooking II'
        dec = None if lv is None else '%d-%d' % (lv // 10 * 10, lv // 10 * 10 + 9)
        out[sheet].append((0, band, (band, lv if lv is not None else 999,
                                     nm.lower()), dec, path))


def tames(out):
    """one sheet per stretch of the run, banded by area and ruled by tier"""
    sheet_of = {area: name for name, areas in TAME_SHEETS for area in areas}
    order = {name: i for i, (name, _) in enumerate(TAME_SHEETS)}
    pins = []
    for path, _ in refs('_Tames.json'):
        nm = path.rsplit('/', 1)[-1]
        area = path.split('/')[0]
        row = TAME.get(nm[len('Boss - '):] if nm.startswith('Boss - ') else nm)
        if row is None:
            raise SystemExit('no Tame row for %s' % nm)
        t = num(row.get('Tier'))
        pins.append((sheet_of.get(area, 'Rune Prana'), area,
                     t if t is not None else 99, nm, path))
    if len(sheet_of) != len({a for _, a, _, _, _ in pins}):
        stray = {a for _, a, _, _, _ in pins} - set(sheet_of)
        if stray:
            raise SystemExit('tame area on no sheet: %s' % sorted(stray))

    # a band sits where the tier you first meet it puts it
    first = {}
    for sheet, area, t, _, _ in pins:
        first[(sheet, area)] = min(first.get((sheet, area), 99), t)
    for sheet, area, t, nm, path in pins:
        out['Tames ' + sheet].append(
            (order[sheet] * 100 + sorted(
                {a for s, a in first if s == sheet},
                key=lambda a: (first[(sheet, a)], a)).index(area),
             area, (t, nm.lower()), t, path))


def main():
    crops, seed_of = crop_order()
    hub = hub_of()
    # a region's place in the run is the tier of what it holds
    per = collections.defaultdict(list)
    for r in SHIP.values():
        t = num(r.get('Tier'))
        if t is not None:
            per[(r.get('Region') or '').strip()].append(t)
    rank = {k: sorted(v)[len(v) // 2] for k, v in per.items()}

    out = collections.defaultdict(list)
    own = []
    for path, _ in refs('_Shipments.json'):
        nm = path.rsplit('/', 1)[-1]
        area = path.split('/')[0]
        boss = nm.startswith('Boss - ')
        row = SHIP.get(nm)
        kind = 'Boss' if boss else ((row.get('Type') or 'Other').strip()
                                    if row else 'Other')
        # a fruit a monster carries is something you kill for, not something you grow
        if kind == 'Fruit' and row and (row.get('Monster') or '').strip():
            kind = 'Drop'
        into = SHEET.get(kind, 'Other')
        t = num(row.get('Tier')) if row else None

        if into in BY_PLACE:
            region = REGION_FIX.get(nm) or ((row.get('Region') or area).strip()
                                            if row else area)
            where = hub(area, region)
            if into == 'Drops' and where == OWN_SHEET:
                own.append((region, kind, nm, path))
                continue
            out[into].append((HUBS.index(where) if where in HUBS else 9, where,
                              (rank.get(region, 99), region, kind, nm.lower()),
                              region, path))
        elif into == 'Crops & Seeds':
            if kind == 'Seed':
                base = seed_of.get(nm)
                at = crops.get(base) if base else None
                key = (at[0] if at else t, at[1] if at else 1 << 29, 0)
            else:
                key = (t, gid(row), 1)
            out[into].append((0, into, key, key[0], path))
        elif into == 'Barn Products':
            mon = (row.get('Monster') or '?').strip() if row else '?'
            out[into].append((0, mon, (mon, t if t is not None else 99), t, path))
        else:
            out[into].append((0, kind, (t if t is not None else 99, nm.lower()),
                              t, path))

    # On its own sheet the areas head their own bands, and a region that is a
    # subdivision of another on the same sheet -- Rune Prana F1 under Rune
    # Prana -- keeps its name in the ruler instead.
    here = {r for r, _, _, _ in own}
    heads = {}
    for region, kind, nm, path in own:
        parents = [p for p in here if p != region and region.startswith(p)]
        head = min(parents, key=len) if parents else region
        heads.setdefault(head, min([rank[r] for r in rank
                                    if r == head or r.startswith(head)] or [99]))
        out['Drops - ' + OWN_SHEET].append(
            (heads[head], head, (rank.get(region, 99), region, kind, nm.lower()),
             None if region == head else region, path))

    crafted(out)
    tames(out)
    doc = {}
    for name in sorted(out, key=lambda k: -len(out[k])):
        doc[name] = [{'path': p, 'band': b, 'sub': s}
                     for _, b, _, s, p in sorted(out[name], key=lambda e: (e[0], e[2]))]
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    print('wrote %s' % os.path.relpath(OUT, PACK))
    for name, v in doc.items():
        print('  %-22s %4d tiles  %2d bands'
              % (name, len(v), len({e['band'] for e in v})))


if __name__ == '__main__':
    main()

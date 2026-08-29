"""Export the RF4 apworld's rules into Lua data tables for the PopTracker pack.

Reads the apworld's own Locations/Items/Regions modules (so the data is exactly
what generation uses) and emits scripts/logic/rf4_data.lua.

Clause encoding (each location/entrance carries an AND-list of these):
  {"R", region}      region is reachable
  {"T", n}           has n distinct area items  (can_reach_tier)
  {"C", recipe}      can_make_recipe
  {"G", item}        can_get_item  (recipe or shipment)
  {"H", item[, n]}   state.has
  {"S", key}         has Rune Sphere >= option <key>  (fortress|runeprana|4)
  {"L"}              has_licenses  (Forging + Crafting)
  {"TT"} / {"MT"}    can_make_top_tool / can_make_mid_tool
  {"P", pct}         ship_percent
  {"O", {clauses}}   OR over clauses
"""
import sys, os, re, json

# the pack root, resolved from this script's own location
PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
sys.path.insert(0, PACK + 'stub')
import importlib
L = importlib.import_module('rf4.Locations')
I = importlib.import_module('rf4.Items')
R = importlib.import_module('rf4.Regions')

# ---------------------------------------------------------------- region graph
exits = {r: list(d.connecting_regions) for r, d in R.region_data_table.items()}

# entrance rules, transcribed from Rules.get_region_rules
ENTRANCE = {
    "Selphia -> Selphia Plains":              [["H", "Volkanon Axe"]],
    "Selphia: Dragon Lake -> Obsidian Mansion": [["H", "Obsidian Bridge"], ["L"]],
    "Selphia -> Floating Empire":             [["S", "fortress"], ["T", 9], ["L"]],
    "Selphia Plains -> Selphia Plains - West": [["H", "Obsidian Bridge"], ["L"]],
    "Yokmir Forest -> Yokmir Cave":           [["H", "Chipsqueek Guide"]],
    "Selphia Plains - West -> Leon Karnak":   [["H", "Etherlink"]],
    "Selphia Plains - West -> Autumn Road":   [["H", "Autumn Bridge"]],
    "Leon Karnak -> Rune Prana":              [["S", "runeprana"], ["T", 10]],
    "Autumn Road -> Maya Road":               [["H", "Maya Bridge"]],
    "Autumn Road -> Silver Lake":             [["H", "Winters Grasp"]],
    "Maya Road (Boss) -> Sechs Territory":    [["H", "Winters Grasp"]],
    "Selphia Plains - East -> Sercerezo Hill":[["H", "Cerezo Bridge"], ["L"]],
    "Selphia -> Sharance Maze":               [["S", 4]],
    "Selphia -> Forge":                       [["H", "Forging License"]],
    "Selphia -> Crafting":                    [["H", "Crafting License"]],
    "Selphia -> Chemistry":                   [["H", "Chemistry License"]],
    "Selphia -> EZ Cooking":                  [["H", "EZ Cooking License"]],
    "Selphia -> Pro Cooking":                 [["H", "Pro Cooking License"]],
    "Selphia -> Selphia Clothing Shop":       [["H", "Clothing Shop"]],
}

# request chain entrances (Rules.get_region_rules tail + request_rule_list)
ship_names = set(L.shipment_data_table)
def request_clause(item):
    if item == "Fenrir":            return ["T", 11]
    if item == "Legendary Sickle":  return ["TT"]
    if item == "Quality Sickle":    return ["MT"]
    if item[:5] == "Ship%":         return ["P", int(item.replace("Ship% ", ""))]
    if item in ship_names:          return ["G", item]
    return ["H", item]

req_entrances = 0
for name, (required_request, item_reqs) in L.request_rules.items():
    if item_reqs:
        ENTRANCE[f"{required_request} -> {name}"] = [request_clause(i) for i in item_reqs]
        req_entrances += 1

# Some locations name a region that does not exist in region_data_table, so a
# literal "R" clause would make them permanently unreachable. Two are obvious
# typos/omissions upstream and are redirected; two are the first requests, which
# are never wired into the request chain and are available from the start.
REGION_ALIAS = {
    "Floating Empire: West": "Floating Empire - West",   # colon vs hyphen upstream
    "Field Dungeon (Boss)":  "Field Dungeon",            # boss sub-region undefined
}
REGION_DROP = {
    "First Task!",                # not in the request chain; available immediately
    "How to place furniture!",
    "Not implemented",            # the Handonetta placeholder, not a real check
}
known_regions = set(R.region_data_table)
unknown_regions = {}

# ------------------------------------------------------------- location clauses
loc_rules = {}          # apid -> list of clauses
# locations are addressed by loc_name in the rules but location_data_table is
# keyed by the raw item name, so accept either.
name_to_apid = dict(L.location_table)                       # loc_name -> apid
for n, d in L.location_data_table.items():
    if d.address:
        name_to_apid.setdefault(n, d.address)               # raw name -> apid

def add(loc_name, clause):
    apid = name_to_apid.get(loc_name)
    if apid is None:
        return False
    loc_rules.setdefault(apid, [])
    if clause not in loc_rules[apid]:
        loc_rules[apid].append(clause)
    return True

# every location needs its own region
for n, d in L.location_data_table.items():
    if not (d.address and d.region):
        continue
    region = REGION_ALIAS.get(d.region, d.region)
    if region in REGION_DROP:
        continue
    if region not in known_regions:
        unknown_regions.setdefault(region, []).append(d.loc_name or n)
        continue
    add(d.loc_name or n, ["R", region])

stats = {}
def bump(k, n=1): stats[k] = stats.get(k, 0) + n

# 1. water shoe chests
WATER_SHOE = [
    "Selphia Plains - West G12 Chest - Leveliser",
    "Selphia Plains - West G12 Chest - Boiled Gyoza Recipe",
    "Selphia Plains - West G12 Chest - Sacred Pole Recipe",
    "Selphia Plains - West G12 Chest - Relax Tea",
    "Autumn Road G1 Chest - Golden Turnip Staff Recipe",
    "Autumn Road G1 Chest - Joy Waterpot Recipe",
    "Autumn Road G1 Chest - Glitter Sashimi Recipe",
    "Autumn Road G1 Chest - Intelligencer",
]
for n in WATER_SHOE:
    if add(n, ["C", "Water Shoes"]): bump("water_shoes")

# NOTE: Rules.get_location_rules() returns a 1-tuple (trailing comma), so the
# `if name in location_rules` test in set_rules is never true and none of those
# 12 rules are applied during generation. Matched here deliberately.

# 2. top crops
for n in L.top_crop_list:
    if add(n, ["O", [["H", "Aquaticus Rain"], ["H", "Fiersome Sun"]]]): bump("top_crop")

# 3. spells
for n in L.spell_list:
    if add(n, ["H", "Magic Shop"]): bump("spell")

# 4. recipes found in chests need the chest's region
for chest_name, recipe_list in L.chest_recipes.items():
    if not recipe_list: continue
    region = L.chest_data_table[chest_name].region
    for recipe in recipe_list:
        if add(recipe, ["R", region]): bump("chest_recipe")

# 5. recipes: craft level + ingredients
for name in L.recipe_levels:
    if add(L.recipe_loc_name[name], ["C", name]): bump("recipe")

# 6. friendship
for name, d in L.friend_data_table.items():
    ln = f"Selphia Friendship - {name}"
    if add(ln, ["T", d.tier]): bump("friend")
    if d.tier >= 2 and d.liked_item: add(ln, ["G", d.liked_item])
    if d.tier >= 5 and d.loved_item: add(ln, ["G", d.loved_item])

# 7. outfits
for name, d in L.outfit_data_table.items():
    if add(f"Selphia Clothing Shop - {name}", ["T", d.tier]): bump("outfit")

# 8. tames
for name, d in L.tame_data_table.items():
    if add(d.loc_name, ["T", d.tier]): bump("tame")
    if d.liked_item: add(d.loc_name, ["G", d.liked_item])
for n in L.boss_tame_list:
    if add(n, ["H", "Pandora's Mandate"]): bump("boss_tame")

# 9. shipment + chest tiers
merged = {**L.shipment_data_table, **L.chest_data_table}
for name, d in merged.items():
    if d.tier:
        if add(d.loc_name, ["T", d.tier]): bump("tier")

# ------------------------------------------------------------------ recipe data
recipes = {n: {"level": int(v[0] / 5), "craft": v[1], "ing": v[2] or []}
           for n, v in L.recipe_levels.items()}
shipments = {n: {"tier": d.tier or 0, "region": d.region}
             for n, d in L.shipment_data_table.items()}

# ------------------------------------------------------------------- emit lua
def lq(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

def clause_lua(c):
    if c[0] == "O":
        return '{"O",{' + ",".join(clause_lua(x) for x in c[1]) + '}}'
    parts = [lq(c[0])] + [(str(x) if isinstance(x, int) else lq(x)) for x in c[1:]]
    return '{' + ",".join(parts) + '}'

# ---------------------------------- item name -> pack item code, for {"H",...}
pack_items = json.load(open(PACK + 'items/items.json', encoding='utf-8-sig'))
pack_codes = set()
for it in pack_items:
    for c in (it.get('codes') or '').split(','):
        if c.strip(): pack_codes.add(c.strip())
    for st in it.get('stages') or []:          # progressive items carry codes per stage
        for c in (st.get('codes') or '').split(','):
            if c.strip(): pack_codes.add(c.strip())

def slug(n): return re.sub(r'[^a-z0-9]', '', n.lower())

has_names = set()
def collect(cs):
    for c in cs:
        if c[0] == "O": collect(c[1])
        elif c[0] == "H": has_names.add(c[1])
for cs in loc_rules.values(): collect(cs)
for cs in ENTRANCE.values(): collect(cs)
has_names |= set(I.area_items)
has_names |= {"Rune Sphere", "Forging License", "Crafting License", "Platinum", "Silver",
              "Forging Level Up", "Crafting Level Up", "Cooking Level Up", "Chemistry Level Up"}

item_code = {n: slug(n) for n in sorted(has_names)}
unresolved = sorted(n for n, c in item_code.items() if c not in pack_codes)

out = []
w = out.append
w("-- GENERATED by tools/export_logic.py from the Rune Factory 4 apworld.")
w("-- Do not edit by hand; re-run the exporter against the apworld source instead.")
w("-- Source: https://github.com/Happyhappyism/Rune-Factory-4-Archipelago")
w("")
w("RF4_AREA_ITEMS = {" + ",".join(lq(x) for x in I.area_items) + "}")
w("")
w("RF4_EXITS = {")
for r in sorted(exits):
    if exits[r]:
        w("    [%s] = {%s}," % (lq(r), ",".join(lq(x) for x in exits[r])))
w("}")
w("")
w("RF4_ENTRANCE = {")
for e in sorted(ENTRANCE):
    w("    [%s] = {%s}," % (lq(e), ",".join(clause_lua(c) for c in ENTRANCE[e])))
w("}")
w("")
w("RF4_RECIPES = {")
for n in sorted(recipes):
    d = recipes[n]
    w('    [%s] = {%d,%s,{%s}},' % (lq(n), d["level"], lq(d["craft"]),
                                    ",".join(lq(i) for i in d["ing"])))
w("}")
w("")
w("RF4_SHIPMENTS = {")
for n in sorted(shipments):
    d = shipments[n]
    w('    [%s] = {%d,%s},' % (lq(n), d["tier"], lq(d["region"])))
w("}")
w("")
GD = importlib.import_module('rf4.game_data')
w("RF4_TOTAL_SHIPMENTS = %d" % GD.game_consts["total shipments"])
w("")
w("RF4_ITEM_CODE = {")
for n in sorted(item_code):
    w("    [%s] = %s," % (lq(n), lq(item_code[n])))
w("}")
w("")
w("RF4_LOC = {")
for apid in sorted(loc_rules):
    w("    [%d] = {%s}," % (apid, ",".join(clause_lua(c) for c in loc_rules[apid])))
w("}")
w("")

path = PACK + 'scripts/logic/rf4_data.lua'
open(path, 'w', encoding='utf-8', newline='\r\n').write("\n".join(out))

print("wrote", path)
print("  regions with exits :", sum(1 for r in exits if exits[r]))
print("  entrance rules     :", len(ENTRANCE), f"({req_entrances} from the request chain)")
print("  recipes            :", len(recipes))
print("  shipments          :", len(shipments))
print("  locations with rules:", len(loc_rules))
print("  rule sources       :", stats)
print("  item names in rules:", len(item_code))
print("  UNRESOLVED (no pack item):", unresolved)
if unknown_regions:
    print("  regions not in the graph (R clause dropped):")
    for r, locs in sorted(unknown_regions.items()):
        print(f"     {r!r}: {len(locs)} locations e.g. {locs[0]}")

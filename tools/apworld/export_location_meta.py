"""Export the per-location metadata the pack needs to filter its own display.

Five apworld options decide which locations a slot contains but never reach
fill_slot_data, so the pack cannot be told them: grocerysanity, outfitsanity,
max_ship_tier, max_sell_value and max_friendship. This exports the numbers
scripts/location_filters.lua evaluates them against.

Sourced from the apworld's own CSVs wherever they hold the data, rather than by
importing its Python: data/Rune Factory 4 AP - Shipments.csv carries Type, Tier
and Sell, and data/Rune Factory 4 AP - Tame.csv carries Tier. Reading those
directly means this script needs no BaseClasses/worlds stubs -- only the CSVs
themselves.

Friendship and outfit locations have no CSV; Locations.py generates them from
two dicts in game_data.py, which imports nothing but `copy`, so that one module
is imported and the two address formulas reproduced below. They are checked
against scripts/autotracking/location_mapping.lua, so a change to either
formula upstream fails loudly here instead of silently exporting wrong ids.

Column conventions, matching Locations.py parse_shipment/parse_tame exactly:
    APID   hexadecimal
    Tier   decimal, blank means 0
    Sell   decimal, blank means 0

The filters, from the apworld's __init__.py:

    shipments  sell_value and sell_value >= max_sell_value  -> dropped
               tier       and tier       >= max_ship_tier   -> dropped
    tames      tier > max_ship_tier                         -> dropped
    friendship tier > max_friendship                        -> dropped

Note the asymmetry: shipments use >=, tames and friendship use >, and a falsy
(zero) shipment tier or sell value is never filtered at all.

Writes scripts/autotracking/location_meta.lua.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, HERE)
from load import apworld, csv_rows                  # noqa: E402

AP = apworld()


def num(v, base=10):
    v = (v or '').strip()
    if not v:
        return 0
    try:
        return int(v, base)
    except ValueError:
        return 0


# ------------------------------------------------------------------ from CSV
ship_tier, ship_sell, grocery = {}, {}, {}
GROCERY_TYPES = {"Product", "Grocery", "Fruit", "Bread", "Tool"}
for row in csv_rows('Shipments', strip_slashes=True):
    apid = num(row.get('APID'), 16)
    # Locations.py builds shipment locations `if data.shipable == True`, and
    # parse_shipment treats anything but the literal "FALSE" as shipable.
    if not apid or (row.get('Shipable') or '').strip() == 'FALSE':
        continue
    tier, sell = num(row.get('Tier')), num(row.get('Sell'))
    if tier:
        ship_tier[apid] = tier
    if sell:
        ship_sell[apid] = sell
    if (row.get('Type') or '').strip() in GROCERY_TYPES:
        grocery[apid] = 1

tame_tier = {}
for row in csv_rows('Tame'):
    apid, tier = num(row.get('APID'), 16), num(row.get('Tier'))
    # Locations.py builds tame locations `if data.liked_item is not None`.
    # "Not implemented" is the Handonetta placeholder, dropped here for the same
    # reason tools/apworld/export_logic.py lists it in REGION_DROP -- it is not a check.
    if (apid and tier and (row.get('Friend Item') or '').strip()
            and (row.get('Region') or '').strip() != 'Not implemented'):
        tame_tier[apid] = tier

# ----------------------------------------------- generated, not in any CSV
game_data = AP.game_data

# Locations.py: ap_address = 0x1C4300 + (index * 0x10) + level, level 0..9
FRIEND_BASE = 0x1C4300
friend_tier = {}
for _name, index in game_data.friendsanity_data.items():
    for level in range(10):
        friend_tier[FRIEND_BASE + (index * 0x10) + level] = level + 1

# Locations.py: ap_address = 0x1C45D0 + index, in dict order
OUTFIT_BASE = 0x1C45D0
outfit = {OUTFIT_BASE + i: 1 for i in range(len(game_data.outfit_data))}

# --------------------------------------------------------------- verify ids
known = set(int(x) for x in re.findall(
    r'\[(\d+)\]', open(PACK + 'scripts/autotracking/location_mapping.lua',
                       encoding='utf-8').read()))
problems = []
for label, ids in (("friendship", friend_tier), ("outfit", outfit)):
    stray = sorted(i for i in ids if i not in known)
    if stray:
        problems.append(f"{len(stray)} derived {label} ids are not in "
                        f"location_mapping.lua (first: {stray[:3]}); the address "
                        f"formula in Locations.py has probably changed")
for label, ids in (("shipment tier", ship_tier), ("tame tier", tame_tier),
                   ("grocery", grocery)):
    stray = sorted(i for i in ids if i not in known)
    if stray:
        problems.append(f"{len(stray)} {label} ids from the CSV are not mapped "
                        f"in the pack (first: {stray[:3]})")
if problems:
    for p in problems:
        print("WARNING:", p, file=sys.stderr)


def emit(f, name, d, comment):
    f.write(f"\n-- {comment}\n{name} = {{\n")
    for apid in sorted(d):
        f.write(f"    [{apid}] = {d[apid]},\n")
    f.write("}\n")


out = PACK + 'scripts/autotracking/location_meta.lua'
with open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write("-- GENERATED by tools/apworld/export_location_meta.py from the Rune Factory 4 apworld.\n")
    f.write("-- Do not edit by hand; re-run the exporter against the apworld source instead.\n")
    f.write("-- Shipment and tame rows come straight from the apworld's CSVs; friendship and\n")
    f.write("-- outfit ids are generated, and are checked against location_mapping.lua.\n")
    f.write("-- Source: https://github.com/Happyhappyism/Rune-Factory-4-Archipelago\n")
    emit(f, "RF4_SHIP_TIER", ship_tier,
         "shipment location -> tier; dropped when tier >= max_ship_tier")
    emit(f, "RF4_SHIP_SELL", ship_sell,
         "shipment location -> sell value; dropped when sell >= max_sell_value")
    emit(f, "RF4_TAME_TIER", tame_tier,
         "tame location -> tier; dropped when tier > max_ship_tier")
    emit(f, "RF4_FRIEND_TIER", friend_tier,
         "friendship location -> level; dropped when level > max_friendship")
    emit(f, "RF4_GROCERY_LOC", grocery,
         "Product/Grocery/Fruit/Bread/Tool shipments; dropped when grocerysanity is off")
    emit(f, "RF4_OUTFIT_LOC", outfit,
         "outfit locations; dropped when outfitsanity is off")

print(f"wrote {out}")
for label, d in (("shipment tiers", ship_tier), ("shipment sells", ship_sell),
                 ("tame tiers", tame_tier), ("friend levels", friend_tier),
                 ("grocery locs", grocery), ("outfit locs", outfit)):
    print(f"  {label:16}{len(d):5}")
print("  " + ("id checks passed" if not problems else f"{len(problems)} WARNING(S) above"))

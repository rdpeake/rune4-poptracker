# Logic pipeline

The pack's access logic is generated from the Rune Factory 4 apworld rather than
hand-written, so it can be regenerated when the apworld changes.

Source: <https://github.com/Happyhappyism/Rune-Factory-4-Archipelago>

## Regenerating

Nothing that is not ours to redistribute is committed, so the tools are grouped
by what they need and each group reads one gitignored folder you fill in:

    tools/apworld/    needs the apworld  -> _input/rf4.apworld (or rf4/)
    tools/            needs neither: works from what is already committed

`tools/apworld/_input/` takes the `.apworld` Archipelago ships, as a zip — the
apworld reads its own CSVs through `pkgutil`, which reads out of a zip fine — or
an unpacked `rf4/`. The few Archipelago classes it imports are stubbed in
`tools/apworld/_stubs/`, which IS committed, so the apworld is the only thing to
supply, and `tools/apworld/load.py` finds it either way.

Every script finds the pack root from its own path, so they run from anywhere.

1. `apworld/export_logic.py` → `scripts/logic/rf4_data.lua`
   The region graph, entrance rules, recipe and shipment tables, and one AND-list
   of clauses per AP location id.
2. `apworld/export_location_meta.py` → `scripts/autotracking/location_meta.lua`
   Per-location tier, sell value, friendship level and the grocery/outfit
   category sets, for the five apworld options that decide the location pool
   but never reach `fill_slot_data`: `grocerysanity`, `outfitsanity`,
   `max_ship_tier`, `max_sell_value` and `max_friendship`.
   Read from the apworld's own CSVs rather than by
   importing its Python, so this one needs no `BaseClasses` stub. Friendship
   and outfit locations have no CSV — `Locations.py` generates them from two
   dicts in `game_data.py` — so that module is imported (it depends on nothing
   but `copy`) and the two address formulas are reproduced, then checked
   against `location_mapping.lua` so an upstream change to either fails loudly
   rather than exporting wrong ids.
   `scripts/location_filters.lua` evaluates these against the pack's own
   settings when offline; when connected the room's location list answers
   directly and the settings panel is filled back in from it.
3. `apply_rules.py` → rewrites `locations/*.json`
   Tags every mapped section with `"^$RF4Access|<ap id>"` and
   `"$RF4Visible|<ap id>"`, resolved through
   `scripts/autotracking/location_mapping.lua`. The `^` on the access rule is
   required: without it PopTracker reads the return as an item count, and a
   SequenceBreak (5) is just "5 >= 1" and paints green. The visibility rule
   must NOT have one — it resolves through the count branch and returns 0 or 1.
4. `apworld/export_location_options.py` -> `scripts/autotracking/option_for_location.lua`,
   `scripts/autotracking/barrier_meta.lua` and `generated/location_kinds.json`
   Which sanity option gates each check, and what each check is, from the
   apworld's own `loc_type`. Which kinds are an object placed in a room is
   discovered rather than listed -- such a kind has a data table whose entries
   carry a field flag -- so a kind the apworld adds is picked up on its own.
5. `apworld/export_barriers.py` -> `locations/*.json` and `location_mapping.lua`
   The barrier, box and search checks: each is one object in one room, so they
   group per region and per room the way chests do. `generated/room_pins.json`
   says where that room is drawn, so the two join on the map id. A room the
   game never draws gets a section on the region's aggregate pin instead, and
   is promoted by `rooms.json` gaining that map id.

`scripts/logic/rf4_rules.lua` evaluates the clauses at runtime and is hand-written.

## Request events

`tools/apworld/export_requests.py` emits one toggle per request into `items/events.json`,
the `Requests` tab grid into `layouts/events.json`, and the region-to-code table
into `scripts/logic/request_events.lua`. A toggled request seeds the
reachability sweeps directly, because a request you have handed in is somewhere
you have already stood -- its predecessors may be unreachable by rule and it
still got done.

**Icons, still to do.** All 93 share `images/settings/opt_requestsanity.png`.
## The game's own tables

The tools that read the game need `bundleMain.mbundle` from a Rune Factory 4
Special install, dropped in `tools/gamedata/_input/`:

    tools/gamedata/   needs the game files -> _input/bundleMain.mbundle

`extract_textures.py` unpacks the minimap art, item icons, frame and font out of
it into the same folder, so that is the only file to find. `paths.py` names what
is missing rather than failing somewhere further in. None of it is
redistributed with the pack.

`tools/room_ids.json` is room id -> map resource name, the table the client's
room numbers index. It came out of `g_mapResourceTable` in live debuggee memory,
each entry dereferenced through the archive TOC, so unlike everything else here
it cannot be re-derived from files on disk -- which is the reason to keep it.
Read it through `tools/room_ids.py`.

`extract_map_graph.py` reads the game's own room adjacency out of the bundle.
The graph is not committed -- run the tool when something needs it. It has
two halves:

    walk   1456 edges  ordinary exits -- you walked through a door
    warp      9 edges  event and one-way links: the Obsidian Mansion drops,
                       Yokmir Forest A08 into MAP_FIELD_35, Selphia into
                       Maya Road

Only `walk` may be used to reason about what is next door: a warp says nothing
about adjacency. The file docstring explains the container and the .rf4m chunk
format.

`read_minipos.py` reads `rf3MapMiniPos.bin`, the game's own table of which
rooms are drawn on which minimap and where. A room's drawn area is its
fog-of-war reveal box, not the record's origin: the two differ on 611 of the
651 maps that have one.

## Redrawing the maps from the game's art

The maps are composed, not captured: the minimap panel `bg_map_03` as the frame,
the `mini_map_*` texture as the art, room labels and caption drawn on top.

Four files, and only two of them are written by hand.

    tools/rooms.json         AUTHORED. Per map id: what the pack calls the room,
                             whether to draw it, and where in the room the label
                             sits. `map id -> {label, show, anchor}`.
    tools/map_art.json       AUTHORED in part: which mini_map_* texture(s) draw
                             each pack image. The rects are computed by
                             `map_art.py --write` -- centred, filling the frame.
    tools/generated/room_positions.json GENERATED by derive_rooms.py: map -> label -> x,y
    tools/generated/room_extents.json   GENERATED likewise: map -> label -> w,h

`rf3MapMiniPos.bin` supplies the geometry (`read_minipos.py`): each room's
fog-of-war box on its sheet. A label goes in the middle of that box unless
`rooms.json` gives it an anchor, which is how a label ends up legitimately off
the road -- a stairway is drawn outside the room it belongs to, and Obsidian
Mansion's corridors are one room wide so their labels are written beside them.

Whether a label is drawn is the `show` field, not a naming rule.

Run order:

    python3 tools/gamedata/map_art.py --write   # only if a placement should change
    python3 tools/gamedata/derive_rooms.py --write
    python3 tools/gamedata/export_transitions.py --write
    python3 tools/gamedata/render_maps.py --out images/maps

`export_transitions.py` reads every doorway in the game's map files whose two
ends are drawn on different pack maps into `generated/transitions.json`: source
map -> destination map -> the rooms you leave from. That is where an area is
entered, which was being placed by eye before.

**Adding a map**: put its image in `maps/maps.json` and a tab in
`layouts/tabs.json`, name its texture in `map_art.json`, give its rooms labels
in `rooms.json`, then run the tools above.

## Chests the map files place somewhere else

Every chest is an object in a room of the map files and
`generated/check_rooms.json` joins it to that room, so a pin no longer depends on
the `Room Code` in the sheet. 147 of the 181 agree outright. The rest are recorded
here because the AP location NAME still carries the sheet's code, so a node
called `A3` can sit on `A2`.

**Two chests the apworld does not list at all.** Both are ordinary chest objects
in rooms the pack draws, and neither flag is claimed by the barrier or box
tables:

    flag 290   byte 224 mask 04   MAP_DUNG_K12   Maya Road Underground A7-5
    flag 528   byte 242 mask 01   MAP_DUNG_M62   Rune Prana F5 A2

Each sits immediately after an AP chest in the same area -- 289 is Maya
Underground C3, 527 is Rune Prana F5 C4 -- while the AP ids run straight past
them, so no id was reserved and skipped. Nothing is wrong the other way: all 181
rows resolve to a real chest object.

**20 the game puts in another room of the same map.** The pin follows the game;
the name still says the left column. `Selphia Plains - West` draws on the Autumn
Road map, which is why those four look like they change area and do not.

    Autumn Road G11            ->  G10   Screw Rock Lv.1
    Autumn Road G8             ->  G7    Dark Ball Lv.2
    Leon Karnak B3             ->  B2    Sunspot
    Leon Karnak D2             ->  D3    Darkness Lv.5
    Rune Prana F4 A2           ->  B3    Pineapple Juice Recipe + Magical Potion x2 + Orichalcum + Leveliser
    Rune Prana F7 A1           ->  B1    Executioner Recipe + Rune Edge Recipe
    Rune Prana F7 A1           ->  B1    Royal Garter Recipe
    Rune Prana F7 B6           ->  D7    Crown Recipe
    Rune Prana F7 B6           ->  D7    Magic Broom Recipe + Hand of God Recipe
    Sechs Territory F1 D5      ->  E3    Water Crystal x4 + Big Crystal
    Sechs Territory F1 E3      ->  D5    Throwing Ring
    Sechs Territory F2 D1      ->  C5    Mystery Potion x4
    Selphia Plains - West G12  ->  G11   Boiled Gyoza Recipe
    Selphia Plains - West G12  ->  G11   Leveliser
    Selphia Plains - West G12  ->  G11   Relax Tea
    Selphia Plains - West G12  ->  G11   Sacred Pole Recipe
    Water Ruins A3             ->  A2    Battle Axe
    Water Ruins A3             ->  A2    Para-Gone + Roundoff
    Water Ruins D6             ->  D5    Blue Ribbon
    Yokmir Cave F3 F2          ->  E2    Bronze Bracelet + Staff

Sechs Territory F1's D5 and E3 hold each other's chest, which reads as one
transposition rather than two mistakes. Water Ruins A3 is not really wrong -- the
A row is a single room spanning three cells and the map prints its label in the
middle one.

**1 the game puts in another area.** The chest is outdoors on Sercerezo Hill,
not inside the den.

    Demon's Den A1  ->  Sercerezo Hill #91   Healing Potion x4

**2 whose room the pack draws no map for.** `tools/pin_remap.json` keeps a pin
where the check is named; the Selphia Plains one is inside a house and the
Obsidian Mansion one is in the town its B8 door opens onto.

    Obsidian Mansion B8  ->  MAP_CITY_04   Cure Lv.1
    Selphia Plains D6    ->  MAP_ROOM_15   Shirt

**11 that differ only in what the pack calls the room**, which are not upstream
errors: the pack numbers rooms the wiki never lettered and prefixes Maya Road's
and Sechs Territory's, so no letter code could match.

    Autumn Road I3           ->  #64    7200G
    Autumn Road I4           ->  #54    18600G
    Autumn Road I4           ->  #54    Parallel Laser Lv.2
    Maya Underground (1) C1  ->  A5-4   Delta Strike Lv.1
    Maya Underground (1) C3  ->  A7-7   Mediseal Lv.1
    Sechs Territory F1 I2    ->  W-1    Mystery Potion x3 + Levelizer
    Selphia Plains C1        ->  #19    Reaper Slash Lv.1
    Yokmir Forest C1         ->  3      Potion x3
    Yokmir Forest C4         ->  7      Turnip Seed x4
    Yokmir Forest D1         ->  1      Small Shield
    Yokmir Forest D3         ->  6      Leather boot

## Upstream data bugs the export matches

`parse_csv` keys its rows by `Name`, so where a sheet holds two rows with the
same name the later one silently wins. Shipments has five such pairs — `Gloves`
is both a Craft worth 170 (line 125) and a Forge worth 380 (line 693), and
`Turnip`, `Squid` and `Battle Turnip` each carry a stray "Category" row.
`export_location_meta.py` collapses them the same way, because the seed was
generated from the collapsed table; reading both rows would put 1078 sell
values in the pack against the 1077 generation used.

## Verifying

    lua tests/*_test.lua

The expectations in `tests/rf4_logic_cases.lua` come from executing the apworld's
*own* `Rules.py` functions over the same item states, so the test compares the
port against the real implementation rather than restating it. Rebuild them with
`apworld/export_logic_cases.py` whenever the apworld moves, or the differential
test is comparing against a release the pack no longer follows.

## Known upstream data issues

These are worked around in `apworld/export_logic.py`; they are bugs in the apworld, not
in the pack.

- `Rules.get_location_rules()` returns a 1-tuple (trailing comma), so the
  `if name in location_rules` test in `set_rules` is never true and none of
  those 12 location rules are applied during generation. Matched deliberately.
- Five region names referenced by locations do not exist in `region_data_table`:
  `Floating Empire: West` (colon, should be a hyphen), `Field Dungeon (Boss)`,
  `First Task!`, `How to place furniture!` and `Not implemented`.
- `Grape Tree Seeds` and `Orange Tree Seeds` are required by the
  `Harvest 50 Grapes!` and `Harvest 20 Oranges!` requests but are not items, so
  those requests cannot be satisfied.

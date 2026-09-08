# Logic pipeline

The pack's access logic is generated from the Rune Factory 4 apworld rather than
hand-written, so it can be regenerated when the apworld changes.

Source: <https://github.com/Happyhappyism/Rune-Factory-4-Archipelago>

## Changing a room

A label, an anchor or a `show` flag in `tools/rooms.json` moves the label on the
map, the room's pin, and the name of every barrier and box check in that room.
Those live in different files, so:

    python3 tools/rebuild_rooms.py

runs the eight steps in order and reports any it had to skip. Then:

    python3 tools/verify/check_maps.py

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
## Following the player

`tools/gamedata/export_room_tabs.py` -> `scripts/autotracking/tab_mapping.lua`:
room id -> the path of tab names that opens the map it is drawn on. Nothing
writes that down, so it falls out of the game's minimap table, `map_art.json`,
`maps/maps.json` and the map widgets in `layouts/*.json` in turn. 726 of the
game's 875 rooms get one; a room on a sheet no pack image draws is an interior
and holds whatever map was showing.

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
    python3 tools/export_area_refs.py --write
    python3 tools/move_pins.py --write

`export_transitions.py` reads every doorway in the game's map files whose two
ends are drawn on different pack maps into `generated/transitions.json`: source
map -> destination map -> the rooms you leave from. That is where an area is
entered, which was being placed by eye before.

`move_pins.py` puts each chest, barrier and box on the room the MAP FILES put
it in, not the room its name gives: `generated/check_rooms.json` joins the check
to a map id. The pin is lifted clear of the label and rooms holding several fan
them out, both bounded by the room's own box. A check the game puts in two rooms
gets a pin in each.

An area pin -- `Autumn Road/Leon Karnak` -- is placed the same way, from
`generated/transitions.json`, so the room an area is entered from is the game's
answer rather than whichever room the pin happened to sit nearest.
`tools/pin_doors.json` names the handful the map files have no doorway for --
Revival Cave is a pit -- and the parked pins for Floating Empire, Sharance Maze
and Field Dungeon keep the pin they have.

`export_area_refs.py` rebuilds what those area pins cover. Each is a node whose
sections are all `ref`s into the area it leads to, so it shows how much of the
place behind the door is left; the lists were hand-written and went stale when
the barrier and box checks arrived. Rebuilding them from the tree puts every
floor and sub-room on the pin that leads to it -- the Rune Prana pin covered 81
of its 183 sections before.

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

## Artwork

The item icons and the three crafting grid maps are generated, not drawn, and
both generators are committed because recovering them from a transcript once was
enough. They need node and one package, which is gitignored:

    npm install --prefix tools @napi-rs/canvas

`gen_item_tiles.mjs` draws `images/items/*.png`: a 64px rounded tile per item,
the background keyed to the item's category family and a rim keyed to its
classification. Input is a JSON list of `{slug, label, cat, cls}`.

`export_grid_maps.py` (which calls `gen_grid_maps.mjs`) rebuilds all eighteen
sheets — eight shipment, five crafting and five tame — **and** checks the pins on
them in `locations/_Crafting.json`, `_Shipments.json` and `_Tames.json`. Image and
pins come out of the same pass, so they must be regenerated together or every pin
slides off its tile. Run it after anything that touches `images/items/` or
`images/monsters/`.

The shipment and crafting sheets are laid out from `generated/grid_layout.json`
(`apworld/export_grid_layout.py`): which sheet a check belongs on, which band
inside it, and in what order. The tame sheets have no plan, so they keep the
order of the pins already on disk and a rebuild changes only the tiles.
Either way the pins are tied to marker positions, so the tool recomputes them and
**refuses to write if any would move** — pass `--relayout` when moving them is the
point.

A band's label sits in the left gutter; under the tiles, a ruler brackets each
run of equal `sub` and names it. That is where the tier goes on the shipment
sheets, so a sheet reads left to right as progression and the tail past your
max-shipment-tier is visible at a glance.

`export_section_icons.py` gives each check its own icon in the tracker instead of
one shared crate: shipments take their item tile, tames their monster tile,
villagers their portrait, boxes the crate texture and barriers the glow columns. PopTracker looks the image
up on the section a `ref` points AT (`maptooltip.cpp:145`), so writing it on the
canonical section in the region file reaches the grid-sheet pins too. Friendship
and box checks are written on the LOCATION instead -- all ten of a villager's
heart levels want the same portrait -- which a section with no image of its own
inherits (`locationsection.cpp:61`). The opened icon is the closed one at 72%
brightness, the relationship the paw, chest and shipment pairs already had.
Map markers are drawn as coloured shapes and never use these images at all.

`export_npc_icons.py` cuts the villager portraits, the box crate and the barrier
out of the bundle. The dialogue portraits are two layers and neither is a portrait alone --
for about half the cast the hair lives in the body layer, so a face-layer icon
comes out bald -- so the head is cropped off the top of `NN_<NAME>_body_00`
instead, sized from the bounding box of the figure's top quarter rather than a
fixed fraction. Six characters are tuned by hand and Ventuswill, whose body is
drawn faceless, has her face composited in from a written-down box.

The barrier is not artwork at all. `efc_mGen_wall_red` is a **parameter
texture**: its red channel is a flat 100% and carries no shape, while green,
blue and alpha hold three different falloffs for the shader to blend, and the
colour comes from the material. Read as RGB it gives a white-hot core the
barrier never has in game, so the icon takes the alpha channel as an intensity
mask -- green and blue carry a comb of teeth and a floor that tints the whole
quad -- mirrors it into an arc, tints it the amber a barrier actually peaks at
on screen, and stacks a second arc a quarter above. `MOBJ_CLEAR_WALL` sounds
like the barrier and is empty; `MOBJ_FID_WALL_*` is the rubble blocking a
field-dungeon room's edges.

Regenerating the shipped files and diffing is the test to run before trusting a
change: they come back byte-identical.

`extract_textures.py` pulls any named texture out of the bundle. Most are BC7 at
1 byte/pixel, but the **map art is uncompressed at 4 bytes/pixel** -- the tool
used to silently skip all 104 of those, and now handles both. Two finds worth
knowing about, written up here:

- `bg_map_03.texture` is the **minimap container** the game draws in the corner
  of the field screen: 482x432 of content in a 512 square, a pale yellow-green
  body at alpha 0.80 with a dotted grid, and the green banner with the leaf
  flourish under it. Its aspect is within 0.1% of the pack's own map canvas.
- `mini_map_*.texture` is the **map art itself**, one 512px texture per floor.
  RGB is flat cream-on-brown; alpha is a soft silhouette, and the gold outline is
  just the brown ground showing through the alpha ramp. Upscaling needs the alpha
  re-sharpened (`-channel A -level 46%,54%`) or the outline goes blobby.


## Verifying

    lua tests/*_test.lua                     the logic port and the Lua scripts
    python3 tools/verify/check_maps.py       the maps and where the pins sit

`check_maps.py` answers two questions. Does re-rendering still produce the
images that are committed? It copies the pack's maps into `_baseline/`, renders
them fresh and compares. And is every pin and room label on drawn road? It walks
them against the art, skipping the aggregates -- a region's shipment and tame
pins, and the area pins, none of which sit in one room -- and reports anything
else that is off it.

The 26 that are off it for good reasons are listed in
`tools/verify/accepted_off_art.json`, which IS committed: a room label nudged
onto the frame, a villager column beside the town, an entrance pin on its icon.
`--accept` rewrites that list from what the current run found, so read what it
reports before running it. `--mark DIR` writes out any map with a new one, the
offending point ringed.

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

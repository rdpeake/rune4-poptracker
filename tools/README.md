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
the `Requests` tab grid into `layouts/events.json` -- once per panel shape, 9,
11 and 21 items to a row -- and the region-to-code table
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
same name the later one silently wins. Shipments has four such pairs — `Turnip`,
`Squid` and `Battle Turnip` each carry a stray "Category" row, and `Venti's
Charm` is in twice as a Craft. None of them costs anything today: the row that
wins is the real one in each case, and the shadowed row is non-shipable, so no
location and no sell value is lost. `Gloves` was the pair that did cost one, and
upstream split it into `Gloves (Accessory)` and `Gloves (Weapon)`.

## Artwork

The item icons and the three crafting grid maps are generated, not drawn, and
both generators are committed because recovering them from a transcript once was
enough. They need node and one package, which is gitignored:

    npm install --prefix tools @napi-rs/canvas

`gen_item_tiles.mjs` draws `images/items/*.png`: a 64px rounded tile per item,
the background keyed to the item's category family and a rim keyed to its
classification. Input is a JSON list of `{slug, label, cat, cls}`.

`export_grid_maps.py` (which calls `gen_grid_maps.mjs`) rebuilds all twenty
sheets — eight shipment, six crafting and six tame — **and** checks the pins on
them in `locations/_Crafting.json`, `_Shipments.json` and `_Tames.json`. Image and
pins come out of the same pass, so they must be regenerated together or every pin
slides off its tile. Run it after anything that touches `images/items/` or
`images/monsters/`.

Every sheet is laid out from `generated/grid_layout.json`
(`apworld/export_grid_layout.py`): which sheet a check belongs on, which band
inside it, and in what order. The pins are tied to marker positions, so the tool
recomputes them and **refuses to write if any would move** — pass `--relayout`
when moving them is the point.

A band's label sits in the left gutter; under the tiles, a ruler brackets each
run of equal `sub` and names it. That is where the tier goes on the shipment
sheets, so a sheet reads left to right as progression and the tail past your
max-shipment-tier is visible at a glance.

### How wide a sheet is

PopTracker scales a sheet to fit its map pane, and **the pane is wide**: with
the horizontal layout in a 1500x950 window it measures 1490x560. Measured under
Xvfb, not guessed — a sheet at 24 columns came out 1322 wide and 1116 tall,
which the pane shrank to half size while leaving 800px of itself empty either
side. Height is what binds, so the sheet that reads best is the SHORT wide one.

A sheet marked `fit` therefore chooses its own column count: `gen_grid_maps.mjs`
lays it out at every width from 16 to 40 columns and keeps the one whose tiles
draw biggest in that pane, stopping at native size rather than asking for an
upscale (ties go to the wider sheet, which is the one that uses the pane). Only
the crafted sheets are marked — they are the ones carrying a chip strip, and
the shipment sheets keep the 24 columns their pins were laid out with.

Splitting a sheet is the other half of the same job, and the cheaper half is
width: Forge I went from half size to 0.82 by widening alone. Crafting still
had to be cut in two, with Accessories — 69 of its 155 tiles — on its own sheet.

### The tame sheets

They were the last family filed by the doorway: five sheets named for the
overworld hub a place is reached through, which put Rune Prana's 32 tames under
a tab called Autumn Road and 86 of the 149 on that one sheet. They are six
sheets now, each named for an area ON it, holding the areas walked in the same
stretch of the run, banded by area and ruled by tier — so the tail past
`max_ship_tier` reads as a bracket rather than as tiles with no marker above
them. Tames are cut on `> tier` where shipments are cut on `>=`, and at the
default of 9 that is 37 of them: Rune Prana entire, Sharance Maze, and the last
two of Leon Karnak.

An area is never split across two sheets. Cutting strictly on tier balances the
sheets better and lands the cut exactly on a tab boundary, but it shreds a
dungeon across tabs — a trial sheet of tiers 4-6 came out eleven bands for 35
tiles, six of them one tile tall.

### What tames a monster

Not the Tame CSV's `Friend Item`. The game lists up to **four** gifts per
monster where the CSV keeps one, and 114 of the pack's 149 tames have more than
one -- which is the difference between a useful pin and a misleading one in a
randomiser, where the four arrive in any order or not at all.

    python3 tools/gamedata/export_monster_presents.py   -> generated/tame_gifts.json
    python3 tools/gamedata/export_chips.py              -> images/chips/
    python3 tools/export_tame_gifts.py                  -> names the pins

`rf3MonsterPresent.bin` holds 209 records of 4 x (item id, value), indexed by
**monster id - 48**; `rf3TxtNpc_split2_1.eng` and `rf3TxtItem_split2_1.eng`
name the monster and the item. The offset came from a histogram of (record
index - monster id) over the 149 gifts the apworld already knew: it is the only
one that puts every one of them in its own monster's record. An empty record is
a monster that cannot be tamed, which agrees with the CSV on every one of them.
The exporter's docstring records what the value means and what the table is not.

The gifts stay in the game's slot order, which runs easiest-first where that
matters -- Buffamoo reads Milk (S) before Milk (L), and ranking by value would
put the milk you cannot get yet at the front.

Tiles draw `images/chips/`, bare icons cut from the game rather than the
`images/items/` cards: at the size four of them fit, a card is mostly frame.
The strip sits under the face, never over it -- a chip riding the tile's edge
reads as its neighbour's -- and only a sheet that has chips reserves the height,
so the shipment sheets keep the pitch and the pins they already had.

The names ride the pin for free. `MapTooltip` prints a `ref` section's own name
when it has one and the target's only when it does not (`maptooltip.cpp:112`),
and that line was pure duplication -- the header already says
`Water Ruins > Tame > Goblin` and the section under it said `Goblin` again. It
now reads `Goblin - gifts: Warrior's Proof, Glue, Old Bandage, Onigiri`.

`MapTooltip` prints a `ref` section's own name when it has one and the target's
only when it does not (`maptooltip.cpp:112`), and that line was pure duplication
— the header already says `Floating Empire > Tame > Blood Panther` and the
section under it said `Blood Panther` again, so the gift costs no pixels. The
name goes on the ref in `_Tames.json`, **never** on the canonical section: a
section's full id is its parent plus its name, so that name IS the ref path
every pin uses and the path `location_mapping.lua` keys the AP id to.

### What a recipe is made of

Not the Recipes CSV's `Ingredients` column, for the same reason as `Friend
Item`. A recipe slot is often a **class** of item -- any Strings, any Minerals
-- and where it is, the CSV names one example instead. The game's Red Ribbon is
`Red Grass + Cloths and Skins + Strings`; the CSV says
`Red Grass + Insect Carapace + Old Bandage`, which in a randomiser reads as a
hunt for one bandage when any string will do. 231 of the pack's 584 badged recipes have
at least one class slot, and Curry Bread is worse still -- the CSV expands its
`Curry` slot into a whole curry recipe.

    python3 tools/gamedata/export_recipes.py            -> generated/recipes.json
    python3 tools/gamedata/export_chips.py              -> images/chips/
    python3 tools/export_recipe_needs.py                -> names the pins

`rf3Recipe*.bin` is 22 tables, one per crafting utensil, each `NLCL` + a
24-byte preamble + 20-byte records: `uint16 @4` the item made, `@6` six
ingredient slots, `@18` the record's index. A slot holds an item id or one of
the 19 class pseudo-items the game keeps at ids 1083-1101 -- Minerals, Liquids,
Claws and Fangs, Sticks and Stems, Cloths and Skins, Furs, Strings, Shards,
Powders and Spores, Scales, Shells and Bones, Stones, Turnip, Crystals, Jewels,
Feathers, Jam, Curry, Squid -- which are `I_Catecory00..18` in that order, so a
class has its own icon to badge.

The record layout was **confirmed, not assumed**: with class slots taken as
wildcards, 601 of the 611 recipes agree with the CSV slot for slot and in order.
The ten that do not are the three the CSV expands, two fish the apworld renamed
(`Lover Snapper` -> `Throbby Snapper`), and five alternates the CSV does not
carry at all.

A repeated slot is a quantity -- Hand-Knit Scarf is four Yarn -- so repeats fold
into a count and the tile shows one chip. A result with more than one record has
genuine alternates: Recovery Potion is `Medicinal Herb + Green Grass` OR one
`Blue Grass`. The first is what the tile badges; the pin's name spells out both,
and marks a class slot `any`:
`Red Ribbon - needs: Red Grass, any Cloths and Skins, any Strings`.

Four chips are what a tile's width shows at a readable size, so a fifth and
sixth wrap to a second row of three rather than shrinking all six to 7px. 75 of
the crafted tiles need the second row, and only a sheet that has one pays for
the height.

A sheet that is already paying for it then wraps at **three**, not four: the
row is bought and spent, so a four-chip tile gains nothing by cramming four
into one line at 11px beside a neighbour drawing three at 14. Wrapping it 3+1
costs no height and leaves the sheet two chip sizes -- 18 for one or two, 14
for three to six -- instead of four. The test is `> 4` chips, never "does
anything wrap", which would be circular.

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


## The panel, four ways

PopTracker picks a root layout by window shape: `tracker_horizontal` when the
window is wider than it is tall, `tracker_vertical` when it is not, and
`tracker_default` only if the one it wants is missing. On top of that the
Items Only variant drops the maps and the chroma option repaints the
background, so the same tabs and items are drawn four ways.

Two swaps write layouts at runtime by re-calling `AddLayouts`, the way the
Pokemon FRLG tracker switches its own variants, and they would fight over one
key each. So a root is only a background around a body:

    tracker_default/_horizontal/_vertical/_broadcast   tracker.json, chroma_*
        -> tracker_body_horizontal / _vertical / _broadcast   tracker.json

`chroma_on.json` and `chroma_off.json` redefine the four roots and nothing
else; `items_only.json` redefines the bodies and nothing else, so the two
compose in either order. `scripts/layouts_import.lua` loads the Items Only
bodies for that variant, `scripts/chroma.lua` swaps the roots on the option.

The map pane is what portrait buys. Docking the item panel at the bottom
rather than down the left side takes the pane from 592x1400 to the full window
width, which is what the wide shipment and craft sheets need -- at 5.2:1 they
are drawn to whatever width there is. So the portrait panel is a bottom strip
like the landscape one, with the grid reflowed 16 items to a row instead of
30, and the whole tracker settles at 742px wide instead of 1016.

    landscape   item_panel_horizontal   1020x306 canvas, 30 wide
    portrait    item_panel_narrow        544x525 canvas, 16 wide
    Items Only  item_panel_vertical      408x748 canvas, 12 wide, no maps

A size MUST be on the `canvas`, not the `group` around it: `trackerview.cpp`
sizes a group to its children and ignores width/height. The grid has to fill
its canvas almost exactly -- a column too many is clipped once the group's
padding counts, one too few leaves the header running on past the icons --
which `tests/item_panel_test.lua` checks.

    python3 tools/reflow_item_grids.py

rewrites the 16- and 12-wide item grids from the 30-wide one, so an item is
added in one place. It is a pure rewrap: run over grids it has not changed, it
gives the same bytes back.

## Verifying

    lua tests/*_test.lua                     the logic port and the Lua scripts
    python3 tools/verify/check_maps.py       the maps and where the pins sit
    python3 tools/verify/check_layouts.py    every layout shows the same things
    python3 tools/reflow_item_grids.py --check   the item grids are in step

`check_layouts.py` compares the four arrangements above, which are hand-written
across seven files. The map tab trees must match exactly, titles and order
included. The item and request grids must hold the same items in the same
order, but not the same rows -- they are reflowed. The roots in `tracker.json`,
`chroma_on.json` and `chroma_off.json` must agree bar the background. No
`{"type": "layout", "key": ...}` anywhere may name a key nothing defines,
which is what catches a body or panel renamed in one file only. And no itemgrid
cell may name an item code `items/` does not define -- such a cell draws as a
blank square and says nothing, which is how half of an item rename hides.

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

Bugs in the apworld, not in the pack, confirmed by reading the source at HEAD
(2026-09-08). Where the pack has to do something about one it is worked around
in `apworld/export_logic.py`, and the pack matches generation's actual behaviour
rather than its intent -- a tracker stricter than AP would show reachable checks
as unreachable.

- `Rules.get_location_rules()` returns a 1-tuple (trailing comma), so the
  `if name in location_rules` test in `set_rules` is never true and none of
  those 12 location rules are applied during generation. Matched deliberately.
  Two more faults sit behind it, so the comma cannot be fixed on its own: the
  bodies call `state.has("X", state, player)`, which evaluates against an empty
  counter and is False with every item held, and the keys are not the names
  generation builds -- `Accessory Bread` for `Selphia Shipment - Accessory
  Bread`, and the two chest keys for `Rune Prana F2 B3 Chest - <items>` -- so
  they would still match nothing.
- Three region names referenced by data are absent from `region_data_table`, and
  `create_regions` silently drops any location in a region it does not know:
  `Floating Empire: West` (colon, should be a hyphen -- Dark Slime, in Tame.csv),
  `Field Dungeon (Boss)` (Greater Demon, Grimoire, Octopirate) and
  `Not implemented` (Handonetta). All five are tames, so nothing is lost unless
  tamesanity is on, and Dark Slime is tier 8, so a `max_ship_tier` under 8 drops
  it anyway. `export_logic.py` aliases the first and drops the rest.
- `Grape Tree Seeds` and `Orange Tree Seeds` are required by the
  `Harvest 50 Grapes!` and `Harvest 20 Oranges!` requests, but the items are
  singular -- `Grape Tree Seed` and `Orange Tree Seed`, which is what the game's
  own string table calls ids 0x31E and 0x31D. The requirement falls through to
  `state.has()` on a name no item has, so neither request can be satisfied. The
  fix belongs in the request row: the shipment names are transcribed correctly,
  and renaming them would move an AP item and location name and cost the two
  items their game art, which `export_item_tiles.py` looks up by name.
- `bugged_locs` reads `Mystery Potion x x3`, with a doubled `x`, so it matches no
  location and the Sechs Territory F1 I2 chest the sheet now marks "Not present
  in AP" still generates.
- The shipment caps compare with `>=` where the tame cap uses `>`, so the 16
  tier-11 shipments and Gold Juice (sell 800000) can never be a check in any
  seed: `MaxItemTier` stops at 11 and `MaxSell` at 800000. The pack hides them,
  which is why Emery Flower and every Sharance Maze boss drop but Earthwyrm
  Scale never appear.
- `parse_csv` reads its CSV as `str(bytes)`, so the two non-ASCII names arrive as
  their UTF-8 escapes: `No Rot α` is `No Rot \xce\xb1` in AP. The pack's item
  slugs carry the escape for the same reason.
- The Searchsanity block builds its locations with `loc_type = "box"`, a copy of
  the block above it, so all 28 come back typed as boxes. Nothing upstream reads
  `loc_type`, so it costs only telling them apart; `load.py` retypes them.

Fixed upstream, recorded so the old workarounds are not put back: `requestsanity`
is honoured, the duplicate `Gloves` shipment is split in two, the `Clippers` tool
no longer carries `progression` as its name, and `fill_slot_data` sends six of
the sanity options. `grocerysanity`, `max_ship_tier`, `max_sell_value` and
`max_friendship` still never arrive and are inferred from the room's location
list.

The `Clippers` rename cost three workarounds, all now gone. Its shipment row is
back in `shipment_data_table` under its own name, so `can_get_item` can answer
for it and `Selphia Plains - East Tame - Shmooly` -- which likes Clippers -- is
in logic again; `UPSTREAM_UNREACHABLE` in `tests/rf4_logic_test.lua` is empty.
The pack item's code was the slug of the broken name and is now `clippers`, and
the check under `Selphia/Shipment` is named `Clippers` rather than
`progression`. And `export_item_meta.py` no longer forces a classification onto
it: the word in that cell was the Name column's corruption, not a
classification, and `Items.py` builds every shipable shipment as
`ItemClassification.filler`, so the tile loses its progression rim.

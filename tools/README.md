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

`scripts/logic/rf4_rules.lua` evaluates the clauses at runtime and is hand-written.

## Request events

`tools/apworld/export_requests.py` emits one toggle per request into `items/events.json`,
the `Requests` tab grid into `layouts/events.json`, and the region-to-code table
into `scripts/logic/request_events.lua`. A toggled request seeds the
reachability sweeps directly, because a request you have handed in is somewhere
you have already stood -- its predecessors may be unreachable by rule and it
still got done.

**Icons, still to do.** All 93 share `images/settings/opt_requestsanity.png`.

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

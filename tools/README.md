# Logic pipeline

The pack's access logic is generated from the Rune Factory 4 apworld rather than
hand-written, so it can be regenerated when the apworld changes.

Source: <https://github.com/Happyhappyism/Rune-Factory-4-Archipelago>

## Regenerating

Both scripts import the apworld's own `Locations.py` / `Items.py` / `Regions.py`,
so put a checkout of it at `stub/rf4/` in the pack root. Archipelago itself is not
needed — only small stubs for `BaseClasses` and `worlds.generic.Rules` alongside it.
`stub/` is not committed. Both scripts locate the pack root from their own path, so
they can be run from anywhere.

1. `export_logic.py` → `scripts/logic/rf4_data.lua`
   The region graph, entrance rules, recipe and shipment tables, and one AND-list
   of clauses per AP location id.
2. `apply_rules.py` → rewrites `locations/*.json`
   Tags every mapped section with `"$RF4Access|<ap id>"`, resolved through
   `scripts/autotracking/location_mapping.lua`.

`scripts/logic/rf4_rules.lua` evaluates the clauses at runtime and is hand-written.

## Verifying

    lua tests/rf4_logic_test.lua

The expectations in `tests/rf4_logic_cases.lua` come from executing the apworld's
*own* `Rules.py` functions over the same item states, so the test compares the
port against the real implementation rather than restating it.

## Known upstream data issues

These are worked around in `export_logic.py`; they are bugs in the apworld, not
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

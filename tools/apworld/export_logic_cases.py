"""Export tests/rf4_logic_cases.lua, the expectations for the logic port.

This is the other half of the differential test. Every expected value here comes
from calling the APWORLD'S OWN functions -- Rules.can_make_recipe, can_get_item
and the real entrance lambdas -- over an item state, so tests/rf4_logic_test.lua
compares scripts/logic/rf4_rules.lua against the real implementation rather than
against a restatement of it. Nothing in this file may read the Lua port, or the
test would only be checking the port against itself.

The item states are carried over from the existing cases file rather than
invented afresh, so regenerating after an apworld change moves the expected
values and leaves the inputs alone -- which is what makes the diff readable.

Run after tools/apworld/export_logic.py, from anywhere:  python3 tools/apworld/export_logic_cases.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
sys.path.insert(0, HERE)
from load import apworld, lua_str, slug             # noqa: E402

AP = apworld()
I = AP.Items
L = AP.Locations
R = AP.Regions
RULES = AP.Rules

PLAYER = 1
# scripts/logic/rf4_rules.lua's RF4_OPT defaults, used until a slot supplies its own
FORTRESS, RUNEPRANA = 4, 4


class Opt:
    def __init__(self, v): self.value = v


class Options:
    fortress_runespheres = Opt(FORTRESS)
    runeprana_runespheres = Opt(RUNEPRANA)


class State:
    """Just enough of an Archipelago CollectionState for the rule lambdas."""

    def __init__(self, held):
        self.held = held
        self._reach = None

    def has(self, name, player, count=1):
        return self.held.get(name, 0) >= count

    def has_all(self, names, player):
        return all(self.has(n, player) for n in names)

    def has_any(self, names, player):
        return any(self.has(n, player) for n in names)

    def has_from_list(self, names, player, count):
        return sum(self.held.get(n, 0) for n in names) >= count

    def count(self, name, player):
        return self.held.get(name, 0)

    def can_reach_region(self, region, player):
        if self._reach is None:
            self._reach = self._walk()
        return region in self._reach

    def _walk(self):
        """Regions reachable from Menu, honouring the apworld's entrance rules.

        can_reach_region is asked from inside the entrance lambdas themselves
        (ship_percent sums it over every shipment region), so the frontier is
        grown with the set built so far visible to those calls rather than
        computing it in one pass.
        """
        rules = RULES.get_region_rules(PLAYER, Options())
        self._reach = {"Menu"}
        changed = True
        while changed:
            changed = False
            for region in list(self._reach):
                data = R.region_data_table.get(region)
                if not data:
                    continue
                for nxt in (data.connecting_regions or []):
                    if nxt in self._reach:
                        continue
                    rule = rules.get("%s -> %s" % (region, nxt))
                    if rule is not None and not rule(self):
                        continue
                    self._reach.add(nxt)
                    changed = True
        return self._reach


def h32(names):
    """the rolling hash tests/rf4_logic_test.lua re-computes over the same list"""
    h = 0
    for s in sorted(names):
        for b in s.encode('utf-8'):
            h = (h * 31 + b) % 2147483647
        h = (h * 31 + 1) % 2147483647
    return h


def main():
    cases_path = PACK + 'tests/rf4_logic_cases.lua'
    old = open(cases_path, encoding='utf-8').read()

    # pack item code -> apworld item name, from the table export_logic.py wrote
    data = open(PACK + 'scripts/logic/rf4_data.lua', encoding='utf-8').read()
    blk = data[data.index('RF4_ITEM_CODE = {'):]
    blk = blk[:blk.index('\n}\n')]
    slug_to_name = {m.group(2): m.group(1) for m in
                    re.finditer(r'\["([^"]+)"\] = "([^"]+)"', blk)}
    # that table only carries the items the rules mention. The request events
    # hold others (Popularity), so fall back to the pack's own slug rule over
    # every apworld item.
    for name in I.item_data_table:
        slug_to_name.setdefault(slug(name), name)

    # the item states are kept exactly as they were
    states = []
    for m in re.finditer(r'\{ held=\{(.*?)\}, tier=', old):
        held = {}
        for k, v in re.findall(r'\["([^"]+)"\]=(\d+)', m.group(1)):
            name = slug_to_name.get(k)
            if name is None:
                raise SystemExit('no apworld item for pack code %r' % k)
            held[name] = int(v)
        states.append(held)
    if not states:
        raise SystemExit('no cases found in %s' % cases_path)

    regions = sorted(R.region_data_table)
    recipes = sorted(L.recipe_levels)
    shipments = sorted(L.shipment_data_table)

    out = ['-- GENERATED expectations for tests/rf4_logic_test.lua.',
           '-- Produced by tools/apworld/export_logic_cases.py: each case is an item state, and',
           "-- the expected values come from executing the APWORLD'S OWN Rules.py",
           '-- functions (can_make_recipe / can_get_item / the real entrance lambdas)',
           '-- over that state. Regenerate if the apworld changes.',
           'RF4_TEST_REGIONS = {%s}' % ','.join(lua_str(r) for r in regions),
           'RF4_TEST_RECIPES = {%s}' % ','.join(lua_str(r) for r in recipes),
           'RF4_TEST_SHIPMENTS = {%s}' % ','.join(lua_str(r) for r in shipments),
           'RF4_TEST_CASES = {']
    for held in states:
        st = State(held)
        reach = [r for r in regions if st.can_reach_region(r, PLAYER)]
        made = [n for n in recipes if RULES.can_make_recipe(n, st, PLAYER)]
        got = [n for n in shipments if RULES.can_get_item(n, st, PLAYER)]
        tier = sum(held.get(n, 0) for n in RULES.area_items)
        code = {v: k for k, v in slug_to_name.items()}
        bits = ','.join('["%s"]=%d' % (code[n], c) for n, c in sorted(held.items()))
        out.append('    { held={%s}, tier=%d, nreach=%d, hreach=%d, nrecipes=%d, '
                   'hrecipes=%d, nitems=%d, hitems=%d },'
                   % (bits, tier, len(reach), h32(reach), len(made), h32(made),
                      len(got), h32(got)))
    out.append('}')
    open(cases_path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print('wrote %s' % cases_path)
    print('  cases      %4d' % len(states))
    print('  regions    %4d' % len(regions))
    print('  recipes    %4d' % len(recipes))
    print('  shipments  %4d' % len(shipments))


if __name__ == '__main__':
    main()

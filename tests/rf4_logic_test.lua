-- Test for scripts/logic/rf4_rules.lua, the access logic ported from the apworld.
--
-- The expectations in tests/rf4_logic_cases.lua were produced by running the
-- APWORLD'S OWN Rules.py functions over the same item states, so this is a
-- differential test of the port rather than a restatement of it.
--
-- Run from the pack root with any Lua 5.x:   lua tests/rf4_logic_test.lua

package.path = "./?.lua;" .. package.path

AccessibilityLevel = { None = 0, Partial = 1, Inspect = 2, SequenceBreak = 3,
                       Normal = 6, Cleared = 7 }
local HELD = {}
Tracker = { ProviderCountForCode = function(_, code) return HELD[code] or 0 end }

require("tests.rf4_logic_cases")
require("scripts.logic.rf4_rules")

---same 32-bit rolling hash the generator used, over a sorted name list
local function h32(names)
    table.sort(names)
    local h = 0
    for _, s in ipairs(names) do
        for i = 1, #s do h = (h * 31 + s:byte(i)) % 2147483647 end
        h = (h * 31 + 1) % 2147483647
    end
    return h
end

local fails = 0
local function check(case, field, want, got)
    if want ~= got then
        fails = fails + 1
        print(string.format("  case %2d  %-9s expected %-12s got %s",
                            case, field, tostring(want), tostring(got)))
    end
end

for i, c in ipairs(RF4_TEST_CASES) do
    HELD = c.held
    RF4_Invalidate()

    local reach, recipes, items = {}, {}, {}
    for _, r in ipairs(RF4_TEST_REGIONS)   do if RF4.reachable(r)       then reach[#reach+1] = r end end
    for _, n in ipairs(RF4_TEST_RECIPES)   do if RF4.can_make_recipe(n) then recipes[#recipes+1] = n end end
    for _, n in ipairs(RF4_TEST_SHIPMENTS) do if RF4.can_get_item(n)    then items[#items+1] = n end end

    check(i, "tier",     c.tier,     RF4.tier_count())
    check(i, "nreach",   c.nreach,   #reach)
    check(i, "hreach",   c.hreach,   h32(reach))
    check(i, "nrecipes", c.nrecipes, #recipes)
    check(i, "hrecipes", c.hrecipes, h32(recipes))
    check(i, "nitems",   c.nitems,   #items)
    check(i, "hitems",   c.hitems,   h32(items))
end

-- every location's rule must at least evaluate without error, and a full state
-- must put every location in logic
local total, reachable_all = 0, 0
HELD = RF4_TEST_CASES[2].held      -- the "everything held" case
RF4_Invalidate()
for apid in pairs(RF4_LOC) do
    total = total + 1
    if RF4Access(tostring(apid)) == AccessibilityLevel.Normal then
        reachable_all = reachable_all + 1
    end
end
if reachable_all ~= total then
    fails = fails + 1
    print(string.format("  %d of %d locations out of logic with everything held",
                        total - reachable_all, total))
end

print(string.format("%d cases over %d regions / %d recipes / %d shipments, %d locations",
      #RF4_TEST_CASES, #RF4_TEST_REGIONS, #RF4_TEST_RECIPES, #RF4_TEST_SHIPMENTS, total))
print(fails == 0 and "ALL PASS" or string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

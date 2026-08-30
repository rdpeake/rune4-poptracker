-- Test for scripts/logic/rf4_rules.lua, the access logic ported from the apworld.
--
-- The expectations in tests/rf4_logic_cases.lua were produced by running the
-- APWORLD'S OWN Rules.py functions over the same item states, so this is a
-- differential test of the port rather than a restatement of it.
--
-- Run from the pack root with any Lua 5.x:   lua tests/rf4_logic_test.lua

package.path = "./?.lua;" .. package.path

-- values must match PopTracker's src/core/accessibilitylevel.h; the engine
-- casts our numeric return straight to the enum (tracker.cpp resolveRules)
AccessibilityLevel = { None = 0, Partial = 1, Inspect = 3, SequenceBreak = 5,
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

-- RF4Access's three states: yellow means the region clauses pass but something
-- else does not, so it must agree with eval_clauses on both of the old answers.
local function tally()
    local n = { [AccessibilityLevel.None] = 0,
                [AccessibilityLevel.SequenceBreak] = 0,
                [AccessibilityLevel.Normal] = 0 }
    local bad_green, bad_yellow, bad_red = 0, 0, 0
    for apid, clauses in pairs(RF4_LOC) do
        local lvl = RF4Access(tostring(apid))
        n[lvl] = (n[lvl] or 0) + 1
        local in_logic = RF4.eval_clauses(clauses)
        -- green must mean fully in logic, and fully in logic must mean green
        if (lvl == AccessibilityLevel.Normal) ~= in_logic then bad_green = bad_green + 1 end
        -- yellow requires every region to be at least physically standable
        if lvl == AccessibilityLevel.SequenceBreak then
            for _, c in ipairs(clauses) do
                if c[1] == "R" and not RF4.loosely_reachable(c[2]) then
                    bad_yellow = bad_yellow + 1
                    break
                end
            end
        end
        -- red requires a region the relaxed graph cannot get to either; a region
        -- that is merely out of logic must not be red
        if lvl == AccessibilityLevel.None then
            local walled_off = false
            for _, c in ipairs(clauses) do
                if c[1] == "R" and not RF4.loosely_reachable(c[2]) then
                    walled_off = true
                    break
                end
            end
            if not walled_off then bad_red = bad_red + 1 end
        end
    end
    return n, bad_green, bad_yellow, bad_red
end

for _, ci in ipairs({1, 2, 3, #RF4_TEST_CASES // 2}) do
    HELD = RF4_TEST_CASES[ci].held
    RF4_Invalidate()
    -- in-logic reachability must never exceed physical reachability
    local leaks = 0
    for _, r in ipairs(RF4_TEST_REGIONS) do
        if RF4.reachable(r) and not RF4.loosely_reachable(r) then leaks = leaks + 1 end
    end
    check(ci, "loose", 0, leaks)
    local n, bad_green, bad_yellow, bad_red = tally()
    check(ci, "green",  0, bad_green)   -- Normal iff eval_clauses
    check(ci, "yellow", 0, bad_yellow)  -- no yellow behind an unreachable region
    check(ci, "red",    0, bad_red)     -- no red with every region reachable
    print(string.format("  case %2d  red %5d  yellow %5d  green %5d",
          ci, n[AccessibilityLevel.None], n[AccessibilityLevel.SequenceBreak],
          n[AccessibilityLevel.Normal]))
end

-- RF4Why must describe every check consistently with the level it reports:
-- green says nothing, yellow explains itself, red says it cannot be reached.
for _, ci in ipairs({1, 3}) do
    HELD = RF4_TEST_CASES[ci].held
    RF4_Invalidate()
    local bad_green, bad_yellow, bad_red, empty = 0, 0, 0, 0
    for apid in pairs(RF4_LOC) do
        local lvl = RF4Access(tostring(apid))
        local why = RF4Why(apid)
        if lvl == AccessibilityLevel.Normal then
            if why ~= "" then bad_green = bad_green + 1 end
        elseif lvl == AccessibilityLevel.SequenceBreak then
            if why:sub(1, 12) ~= "Out of logic" then bad_yellow = bad_yellow + 1 end
            if #why < 20 then empty = empty + 1 end
        else
            if why:sub(1, 12) ~= "Out of reach" then bad_red = bad_red + 1 end
        end
    end
    check(ci, "why/green",  0, bad_green)   -- in logic explains nothing
    check(ci, "why/yellow", 0, bad_yellow)
    check(ci, "why/red",    0, bad_red)
    check(ci, "why/detail", 0, empty)       -- no bare stub reasons
end

-- the summary must agree with the per-check levels it claims to summarise
HELD = RF4_TEST_CASES[3].held
RF4_Invalidate()
local counted = 0
for apid in pairs(RF4_LOC) do
    if RF4Access(tostring(apid)) == AccessibilityLevel.SequenceBreak then counted = counted + 1 end
end
local summarised, by = RF4LogicSummary()
check(3, "summary", counted, summarised)
local cats = 0
for _ in pairs(by) do cats = cats + 1 end
check(3, "categories", true, cats > 0)
print("  " .. RF4LogicSummaryText())

-- the empty state must not paint anything yellow behind a wall, and the full
-- state must have no yellow left at all
HELD = RF4_TEST_CASES[2].held
RF4_Invalidate()
local n = tally()
check(0, "allgreen", 0, n[AccessibilityLevel.SequenceBreak])

print(string.format("%d cases over %d regions / %d recipes / %d shipments, %d locations",
      #RF4_TEST_CASES, #RF4_TEST_REGIONS, #RF4_TEST_RECIPES, #RF4_TEST_SHIPMENTS, total))
print(fails == 0 and "ALL PASS" or string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

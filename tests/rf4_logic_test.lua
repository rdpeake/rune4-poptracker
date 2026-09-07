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
require("scripts.logic.request_events")
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

-- LOOSE_BACKTRACK, the one place the pack deliberately diverges: upstream
-- models every exit one way, outward from Selphia, while in game you can walk
-- back. What is pinned here is that it only ever paints yellow.
do
    local hill = {}
    for apid, clauses in pairs(RF4_LOC) do
        for _, c in ipairs(clauses) do
            if c[1] == "R" and c[2] == "Sercerezo Hill" then hill[#hill+1] = apid break end
        end
    end
    local function levels(held)
        HELD = held
        RF4_Invalidate()
        local n = { [AccessibilityLevel.None] = 0, [AccessibilityLevel.SequenceBreak] = 0,
                    [AccessibilityLevel.Normal] = 0 }
        for _, apid in ipairs(hill) do
            local l = RF4Access(tostring(apid))
            n[l] = (n[l] or 0) + 1
        end
        return n
    end
    local code = RF4_ITEM_CODE
    local none = levels({})
    check(0, "walled off with nothing held", #hill, none[AccessibilityLevel.None])

    -- the back route: no Volkanon Axe anywhere in this state
    local back = levels({ [code["Obsidian Bridge"]] = 1, [code["Cerezo Bridge"]] = 1 })
    check(0, "back route reaches the hill", 0, back[AccessibilityLevel.None])
    check(0, "back route is out of logic", #hill, back[AccessibilityLevel.SequenceBreak])
    check(0, "back route is never in logic", 0, back[AccessibilityLevel.Normal])

    -- and the axe alone still is not enough to stand there
    local axe = levels({ [code["Volkanon Axe"]] = 1 })
    check(0, "the axe alone does not open the hill", #hill, axe[AccessibilityLevel.None])
end

-- Requests are a linear chain of one-request regions, and with requestsanity
-- off they are not checks at all, so nothing reports them. The toggles in
-- items/events.json say so directly: marking one done must open its region
-- without any item being held, and must not open anything else.
do
    -- Deterministically: sorted, and the first request that is genuinely shut
    -- with nothing held. next() on a hash table gives an arbitrary key, and
    -- the early requests are reachable for free, so picking one at random made
    -- this pass or fail depending on iteration order.
    local names = {}
    for n in pairs(RF4_REQUEST_EVENT) do names[#names + 1] = n end
    table.sort(names)
    HELD = {}
    RF4_Invalidate()
    local name, code
    for _, n in ipairs(names) do
        if not RF4.reachable(n) then name, code = n, RF4_REQUEST_EVENT[n] break end
    end
    check(0, "req/table", true, #names > 0)
    check(0, "req/found a shut one", true, name ~= nil)
    if name then
        local before = RF4.reachable(name)
        HELD = { [code] = 1 }
        RF4_Invalidate()
        check(0, "req/opens", true, RF4.reachable(name))
        check(0, "req/was shut", false, before)
        -- and it must not hand out anything else for free
        local leaked = 0
        for _, r in ipairs(RF4_TEST_REGIONS) do
            if r ~= name and RF4.reachable(r) then
                HELD = {}
                RF4_Invalidate()
                if not RF4.reachable(r) then leaked = leaked + 1 end
                HELD = { [code] = 1 }
                RF4_Invalidate()
            end
        end
        check(0, "req/no leak", 0, leaked)
    end
    HELD = {}
    RF4_Invalidate()
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

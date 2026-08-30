-- Test for the ACCESS RULE STRINGS in locations/*.json, as opposed to the Lua
-- behind them (tests/rf4_logic_test.lua covers that).
--
-- RF4Access returns an AccessibilityLevel, but PopTracker only reads a Lua
-- return as a level when the rule string starts with "^". Without it the return
-- is treated as an ITEM COUNT and the rule passes whenever it is >= 1, so
-- SequenceBreak (5) silently paints GREEN. Normal (6) and None (0) happen to
-- come out right either way, which is why a two-state RF4Access worked without
-- the prefix and a three-state one does not.
--
-- See PopTracker doc/PACKS.md ("Rules starting with ^ interpret the value as
-- AccessibilityLevel instead of count") and src/core/tracker.cpp resolveRules.
--
-- Run from the pack root:   lua tests/rf4_access_rules_test.lua

local LEVEL = { None = 0, Partial = 1, Inspect = 3, SequenceBreak = 5, Normal = 6, Cleared = 7 }

local fails = 0
local function check(what, want, got)
    if want ~= got then
        fails = fails + 1
        print(string.format("  FAIL  %-58s expected %s, got %s", what, tostring(want), tostring(got)))
    else
        print(string.format("  ok    %-58s %s", what, tostring(got)))
    end
end

-- ---------------------------------------------------------------- rule strings
-- Every RF4Access rule must carry the "^" prefix. Scanned as raw text so a
-- reformat of the JSON cannot hide a missing one.
local dirs = io.popen('ls locations/*.json 2>/dev/null || dir /b locations\\*.json')
local files, total, bare = {}, 0, 0
for line in dirs:lines() do files[#files+1] = line end
dirs:close()

for _, path in ipairs(files) do
    local f = io.open(path, "r")
    if f then
        local body = f:read("a")
        f:close()
        for prefix in body:gmatch('(.)%$RF4Access|') do
            total = total + 1
            if prefix ~= "^" then bare = bare + 1 end
        end
    end
end
check(string.format("%d RF4Access rules across %d files, all ^-prefixed", total, #files), 0, bare)
if total == 0 then
    fails = fails + 1
    print("  FAIL  found no RF4Access rules at all -- is this the pack root?")
end

-- --------------------------------------------------- mirror of resolveRules
-- The subset of src/core/tracker.cpp resolveRules that this pack's rule strings
-- exercise: one ruleset, one rule, either blank or "^$func|arg" / "$func|arg".
local function resolve(rule, lua_return)
    if rule:match("^%s*$") then return LEVEL.Normal end            -- " " is true
    local is_level = rule:sub(1, 1) == "^"
    local n = lua_return
    if is_level then
        return n                                                    -- value IS the level
    end
    return n >= 1 and LEVEL.Normal or LEVEL.None                    -- value is a COUNT
end

-- src/ui/trackerview.cpp CalculateLocationState -> src/ui/mapwidget.cpp StateColors
local function colour(level)
    if level == LEVEL.Normal then return "green" end
    if level == LEVEL.None then return "red" end
    if level == LEVEL.Inspect then return "blue" end
    return "yellow"                                                 -- the "glitched" bit
end

print("\nwith the ^ prefix (what the pack ships):")
check("RF4Access -> Normal        paints", "green",  colour(resolve("^$RF4Access|1", LEVEL.Normal)))
check("RF4Access -> SequenceBreak paints", "yellow", colour(resolve("^$RF4Access|1", LEVEL.SequenceBreak)))
check("RF4Access -> None          paints", "red",    colour(resolve("^$RF4Access|1", LEVEL.None)))

print("\nwithout it, to document the failure mode this test exists to catch:")
check("bare rule turns SequenceBreak into", "green", colour(resolve("$RF4Access|1", LEVEL.SequenceBreak)))
check("bare rule still gets Normal right",  "green", colour(resolve("$RF4Access|1", LEVEL.Normal)))
check("bare rule still gets None right",    "red",   colour(resolve("$RF4Access|1", LEVEL.None)))

print()
print(fails == 0 and "ALL PASS" or string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

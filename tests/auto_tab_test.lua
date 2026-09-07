-- Test for scripts/auto_tab.lua.
--
-- Two jobs are kept apart and are tested apart:
--
--   the badge      unconditional -- the readout used to classify rooms, so it
--                  shows whatever arrived and is gated on nothing.
--   navigation     needs the option on, a numeric id and a known tab path.
--                  Navigating somewhere wrong is worse than not navigating, so
--                  the cases worth pinning are where it stays put.
--
-- Run from the pack root with any Lua 5.x:   lua tests/auto_tab_test.lua

package.path = "./?.lua;" .. package.path

local HINTS, LOG = {}, {}
local AUTOTAB = 0

-- Stand-in for the opt_autotab JsonItem. SetOverlay drops a write matching what
-- is already there (jsonitem.h), which is what stops the badge re-triggering
-- the "*" watch, so the stub counts only writes that would really emit.
local BADGE = { text = "", writes = 0 }
local badge_obj = setmetatable({}, {
    __index = function(_, k) return k == "BadgeText" and BADGE.text or nil end,
    __newindex = function(_, k, v)
        if k == "BadgeText" and v ~= BADGE.text then
            BADGE.text = v
            BADGE.writes = BADGE.writes + 1
        end
    end,
})

Tracker = {
    ProviderCountForCode = function(_, code)
        return code == "opt_autotab" and AUTOTAB or 0
    end,
    UiHint = function(_, name, value) HINTS[#HINTS + 1] = name .. "=" .. value end,
    FindObjectForCode = function(_, code)
        return code == "opt_autotab" and badge_obj or nil
    end,
}

local realprint = print
print = function(...)
    local t = {}
    for i = 1, select('#', ...) do t[i] = tostring((select(i, ...))) end
    LOG[#LOG + 1] = table.concat(t, " ")
end

-- NB: the capture stays installed for the whole run -- auto_tab logs through
-- the global print, so the "logged once" checks need it. The test's own output
-- goes through io.write.
require("scripts.auto_tab")

local fails = 0
local function check(label, want, got)
    local ok = want == got
    io.write(string.format("%-58s %s\n", label, ok and "PASS" or
        string.format("FAIL (want %s, got %s)", tostring(want), tostring(got))))
    if not ok then fails = fails + 1 end
end

local function reset()
    HINTS, LOG = {}, {}
    RF4_ResetMap()
    BADGE.writes = 0
end

---A dropped packet must say something, or a silent early return looks exactly
---like a feature that is not there. What it says is deliberately not pinned:
---asserting log wording tests the strings, not the behaviour.
local function said_something() return #LOG > 0 end

-- a room the generated table knows, and one it does not
local mapped, unmapped
for id in pairs(RF4_TAB_MAPPING) do
    if mapped == nil or id < mapped then mapped = id end
end
for id = 0, 5000 do
    if RF4_TAB_MAPPING[id] == nil then unmapped = id break end
end
io.write(string.format("  mapped room %d = %s -> %s\n", mapped,
    RF4_ROOM_NAME[mapped], table.concat(RF4_TAB_MAPPING[mapped], " > ")))

-- == the badge is unconditional ==========================================
AUTOTAB = 0
reset()
RF4_ShowMapValue(mapped)
check("badges with navigation switched off", tostring(mapped), BADGE.text)

AUTOTAB = 1
reset()
RF4_ShowMapValue(unmapped)
check("badges a room with no tab mapping", tostring(unmapped), BADGE.text)

reset()
RF4_ShowMapValue("0214")
check("shows the value as it arrived, not as parsed", "0214", BADGE.text)

reset()
RF4_ShowMapValue("not a room")
check("shows an unparseable value, truncated to fit", "not a\u{2026}", BADGE.text)

reset()
RF4_ShowMapValue(mapped)
local writes = BADGE.writes
RF4_ShowMapValue(mapped)
RF4_ShowMapValue(mapped)
check("repeating a value does not rewrite the badge", writes, BADGE.writes)

reset()
RF4_ShowMapValue(mapped)
RF4_ShowMapValue(nil)
check("nil clears the badge", "", BADGE.text)

-- == navigation ==========================================================
AUTOTAB = 0
reset()
check("switched off: does not navigate", false, RF4_UpdateMap(mapped))
check("switched off: sends no hints", 0, #HINTS)

AUTOTAB = 1
reset()
check("navigates a mapped room", true, RF4_UpdateMap(mapped))
check("hint count matches the path length", #RF4_TAB_MAPPING[mapped], #HINTS)
check("sends the outermost tab first",
      "ActivateTab=" .. RF4_TAB_MAPPING[mapped][1], HINTS[1])

-- "if we are not already on the relevant map": the test is the tab path, not
-- the room, so moving between two rooms of one map sends nothing
check("the same room again does nothing", false, RF4_UpdateMap(mapped))
local other = nil
for id, tabs in pairs(RF4_TAB_MAPPING) do
    if id ~= mapped and table.concat(tabs, " > ") ==
       table.concat(RF4_TAB_MAPPING[mapped], " > ") then other = id break end
end
if other then
    local before = #HINTS
    check("a different room on the same map does nothing", false, RF4_UpdateMap(other))
    check("and sends no further hints", before, #HINTS)
end

reset()
check("an unknown room does not navigate", false, RF4_UpdateMap(unmapped))
check("an unknown room sends no hints", 0, #HINTS)
check("an unknown room is not dropped silently", true, said_something())

reset()
check("a non-number navigates nowhere", false, RF4_UpdateMap("not a room"))
check("nil navigates nowhere", false, RF4_UpdateMap(nil))
check("neither sends hints", 0, #HINTS)

-- == an unplaced room stays put ==========================================
-- Some rooms the game draws on no minimap the pack has a map for. Nothing to
-- navigate to, so nothing moves -- but the badge still shows the id, which is
-- the number the player reads back.
local unplaced
for id in pairs(RF4_ROOM_NAME) do
    if RF4_TAB_MAPPING[id] == nil and RF4_ROOM_HOLD[id] == nil
       and (unplaced == nil or id < unplaced) then unplaced = id end
end
check("there are rooms with no map at all", true, unplaced ~= nil)
if unplaced then
    AUTOTAB = 1
    reset()
    check("an unplaced room does not navigate", false, RF4_UpdateMap(unplaced))
    check("and sends no hints", 0, #HINTS)
    check("but it is reported", true, said_something())
    reset()
    RF4_OnBounced({ data = { currentMap = unplaced } })
    check("a bounce for an unplaced room still badges it", tostring(unplaced), BADGE.text)
    check("and still does not navigate", 0, #HINTS)
end

-- == interiors hold the current map ======================================
-- The pack has no interior maps, and five houses sit out in the fields, so
-- navigating to Selphia Town on entering one moves the map away from where the
-- player is. Holding beats guessing.
local interior
for id in pairs(RF4_ROOM_HOLD or {}) do
    if interior == nil or id < interior then interior = id end
end
check("the exporter marked interiors to hold", true, interior ~= nil)
if interior then
    AUTOTAB = 1
    reset()
    RF4_UpdateMap(mapped)                       -- somewhere with a real map
    local hints = #HINTS
    check("an interior sends no hints", hints, (function()
        RF4_UpdateMap(interior); return #HINTS end)())
    check("and does not navigate", false, RF4_UpdateMap(interior))
    -- leaving the house and returning to the same map must also stay quiet
    check("returning to the same map after it is a no-op", false, RF4_UpdateMap(mapped))
    check("an interior is not in the tab table", nil, RF4_TAB_MAPPING[interior])
end

-- == packets =============================================================
-- the client sends currentMap; the match is case-insensitive so the exact
-- spelling it settles on does not matter
AUTOTAB = 1
reset()
RF4_OnBounced({ data = { currentMap = mapped } })
check("a currentMap bounce badges", tostring(mapped), BADGE.text)
check("a currentMap bounce navigates", #RF4_TAB_MAPPING[mapped], #HINTS)

reset()
RF4_OnBounced({ data = { CURRENTMAP = mapped } })
check("the field name is matched case-insensitively", tostring(mapped), BADGE.text)

-- a payload the client puts at the top level instead of under data
reset()
RF4_OnBounced({ currentMap = mapped })
check("a top-level map field is found too", tostring(mapped), BADGE.text)

-- an unmapped room is exactly what the readout exists for: badge it, and stay
-- where you are
reset()
RF4_OnBounced({ data = { currentMap = unmapped } })
check("an unmapped room badges", tostring(unmapped), BADGE.text)
check("an unmapped room does not navigate", 0, #HINTS)

reset()
RF4_OnBounced({ data = { source = "someone", time = 1 } })
check("a bounce with no map field badges nothing", "", BADGE.text)
check("and is not dropped silently", true, said_something())

reset()
RF4_OnBounced({})
RF4_OnBounced(nil)
check("junk is survivable", 0, #HINTS)

-- == slot data ===========================================================
reset()
RF4_MapFromSlotData({ currentMap = mapped })
check("slot_data with a map field navigates", #RF4_TAB_MAPPING[mapped], #HINTS)
reset()
RF4_MapFromSlotData({ unrelated = 1 })
check("slot_data without one is ignored", 0, #HINTS)

-- == the entry points are actually reachable from the pack ================
-- Defined, exported and tested counts for nothing if the pack never calls
-- them. The bounce handler is wired up in watches.lua; these two hang off
-- OnClear.
local function file_contains(path, needle)
    local f = io.open(path, "r")
    if not f then return false end
    local body = f:read("a")
    f:close()
    return body:find(needle, 1, true) ~= nil
end

check("RF4_OnBounced is registered as a bounce handler", true,
      file_contains("scripts/watches.lua", "RF4_OnBounced"))
check("RF4_MapFromSlotData is called on connect", true,
      file_contains("scripts/autotracking/archipelago.lua", "RF4_MapFromSlotData"))
check("RF4_ResetMap is called on connect", true,
      file_contains("scripts/autotracking/archipelago.lua", "RF4_ResetMap"))
check("the badge write is kept off the logic hot path", true,
      file_contains("scripts/logic/graph_logic/logic_main.lua", "AUTO_TAB_CODE"))

-- == the report ==========================================================
-- It is driven by a watch on the very item whose badge it writes, so the thing
-- worth pinning is that it settles instead of bouncing.
reset()
AUTOTAB = 1
RF4_ReportAutoTabState()
local settled = #LOG
RF4_ReportAutoTabState()
RF4_ReportAutoTabState()
check("re-entering the report is a no-op", settled, #LOG)

print = realprint
io.write("\n" .. (fails == 0 and "ALL PASS  (0 failures)" or
        string.format("FAILURES (%d)", fails)) .. "\n")
os.exit(fails == 0 and 0 or 1)

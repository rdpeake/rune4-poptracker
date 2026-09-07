-- Test for the hint glow in scripts/autotracking/archipelago.lua.
--
-- The colour of a hint is the pack's only way of saying what was pointed at, and
-- it is easy to break without noticing: the whole feature hangs off a global
-- PopTracker sets up (`Highlight`), a data-storage key spelled by hand, and two
-- handlers registered in watches.lua. Any one of them can go missing and the
-- glow simply never appears, with nothing to say so.
--
-- Run from the pack root with any Lua 5.x:   lua tests/hint_highlight_test.lua

package.path = "./?.lua;" .. package.path

-- the enum poptracker.cpp registers, with the values from locationsection.h
Highlight = { Avoid = -1, None = 0, NoPriority = 1, Unspecified = 2, Priority = 3 }

local SECTIONS = {}
Tracker = {
    BulkUpdate = false,
    FindObjectForCode = function(_, code)
        SECTIONS[code] = SECTIONS[code] or {}
        return SECTIONS[code]
    end,
    ProviderCountForCode = function() return 0 end,
}
Archipelago = {
    PlayerNumber = 1,
    SetNotify = function() end, Get = function() end,
    GetPlayerAlias = function() return "me" end,
}
ScriptHost = {
    AddWatchForCode = function() end, RemoveWatchForCode = function() end,
    AddOnFrameHandler = function() end, RemoveOnFrameHandler = function() end,
    AddOnLocationSectionChangedHandler = function() end,
    CreateLuaItem = function() return {} end,
}
AccessibilityLevel = { None = 0, Normal = 6, Cleared = 7 }
ImageReference = { FromPackRelativePath = function(_, p) return p end }

require("scripts.autotracking.archipelago")

local failures = 0
local function check(what, got, want)
    local ok = got == want
    if not ok then failures = failures + 1 end
    print(string.format("%-58s %s", what, ok and "ok" or
        string.format("FAIL (got %s, want %s)", tostring(got), tostring(want))))
end

-- a real id whose mapping is a section, so the test cannot pass against a stub
local ID, PATH
for id, paths in pairs(LOCATION_MAPPING) do
    if type(paths) == "table" and type(paths[1]) == "string"
            and paths[1]:sub(1, 1) == "@" then
        ID, PATH = id, paths[1]
        break
    end
end
check("a location id maps to a section path", PATH ~= nil, true)

HINTS_ID = "_read_hints_0_1"

-- OnNotify traces every message it is handed; the test is not interested
local say = print
local function quietly(fn, ...)
    print = function() end
    local ok, err = pcall(fn, ...)
    print = say
    if not ok then error(err, 0) end
end

local function hint(status, flags)
    SECTIONS[PATH] = {}
    quietly(OnNotify, HINTS_ID, {{ location = ID, finding_player = 1,
                                   status = status, item_flags = flags }}, {})
    return SECTIONS[PATH].Highlight
end

-- an unclassified hint takes its colour from what the item is
check("progression hint glows Priority (gold)",   hint(0, 1), Highlight.Priority)
check("useful hint glows NoPriority (blue)",      hint(0, 2), Highlight.NoPriority)
check("trap hint glows Avoid (red)",              hint(0, 4), Highlight.Avoid)
check("filler hint glows Unspecified (white)",    hint(0, 0), Highlight.Unspecified)

-- a hint the player has classified keeps that classification
check("a hint marked priority glows Priority",    hint(30, 0), Highlight.Priority)
check("a hint marked avoid glows Avoid",          hint(20, 0), Highlight.Avoid)
check("a hint marked no priority glows NoPriority", hint(10, 0), Highlight.NoPriority)

-- and a hint the server says is found stops glowing
check("a found hint glows None",                  hint(40, 0), Highlight.None)

-- somebody else's hint is not ours to draw
SECTIONS[PATH] = {}
quietly(OnNotify, HINTS_ID, {{ location = ID, finding_player = 2, status = 0,
                               item_flags = 1 }}, {})
check("another player's hint is left alone", SECTIONS[PATH].Highlight, nil)

-- the handlers the glow depends on are actually registered
local watches = io.open("scripts/watches.lua"):read("a")
check("OnNotify is registered as a set-reply handler",
      watches:find("AddSetReplyHandler", 1, true) ~= nil, true)
check("OnNotifyLaunch is registered as a retrieved handler",
      watches:find("AddRetrievedHandler", 1, true) ~= nil, true)

print(failures == 0 and "\nALL PASS  (0 failures)"
      or string.format("\nFAILURES  (%d failures)", failures))
os.exit(failures == 0 and 0 or 1)

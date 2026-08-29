-- Test for scripts/luaitems.lua.
--
-- Guards the bug where CreateLuaManualStorageItem set PotentialCodes from two
-- undefined globals. PopTracker's LuaItem::canProvideCode treats PotentialCodes
-- as authoritative whenever it is set, and never falls back to
-- CanProvideCodeFunc, so an empty list made the item permanently unfindable.
-- Tracker:FindObjectForCode("manual_location_storage") then returned nil and
-- OnClear died on its first line, silently disabling autotracking for the
-- whole session.
--
-- Run from the pack root with any Lua 5.x:   lua tests/luaitems_test.lua

package.path = "./?.lua;" .. package.path

ScriptHost = { CreateLuaItem = function() return {} end }
ImageReference = { FromPackRelativePath = function(_, p) return p end }

require("scripts.luaitems")

local fails = 0
local function check(label, cond, extra)
    print(string.format("%-56s %s", label, cond and "PASS" or "FAIL"))
    if not cond then
        fails = fails + 1
        if extra then print("     " .. tostring(extra)) end
    end
end

local NAME = "manual_location_storage"
local item = CreateLuaManualStorageItem(NAME)

check("item is created", item ~= nil)
check("Name is the code", item.Name == NAME, item.Name)

-- the actual regression
local codes = item.PotentialCodes
check("PotentialCodes is a table", type(codes) == "table")
check("PotentialCodes is not empty", codes and #codes > 0,
      "an empty list makes the item unfindable by FindObjectForCode")
local found = false
for _, c in ipairs(codes or {}) do if c == NAME then found = true end end
check("PotentialCodes contains the item's code", found,
      "got: " .. table.concat(codes or {}, ", "))
for i, c in ipairs(codes or {}) do
    check("  entry " .. i .. " is a string", type(c) == "string", type(c))
end

-- CanProvideCodeFunc must agree with PotentialCodes, since either path may run
check("CanProvideCodeFunc accepts the code",
      item.CanProvideCodeFunc(item, NAME) == true)
check("CanProvideCodeFunc rejects another code",
      item.CanProvideCodeFunc(item, "something_else") == false)
check("ProvidesCodeFunc returns 1 for the code",
      item.ProvidesCodeFunc(item, NAME) == 1)

-- the state OnClear and PreOnClear rely on
check("ItemState exists", item.ItemState ~= nil)
check("MANUAL_LOCATIONS present", type(item.ItemState.MANUAL_LOCATIONS) == "table")
check("MANUAL_LOCATIONS_ORDER present", type(item.ItemState.MANUAL_LOCATIONS_ORDER) == "table")
check("save/load hooks set", item.SaveFunc ~= nil and item.LoadFunc ~= nil)

print(string.format("\n%s  (%d failure%s)", fails == 0 and "ALL PASS" or "FAILURES",
                    fails, fails == 1 and "" or "s"))
os.exit(fails == 0 and 0 or 1)

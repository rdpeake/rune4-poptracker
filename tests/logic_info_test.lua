-- Test for scripts/logic_info.lua, the hoverable out-of-logic summary.
--
-- The thing worth guarding is the feedback loop: StateChanged watches every
-- code ("*"), and assigning BadgeText or Name to a LuaItem emits onChange. If
-- RF4_UpdateLogicInfo wrote unconditionally it would re-trigger the very
-- handler that called it. The writes are therefore guarded on equality, and
-- these tests pin that.
--
-- Run from the pack root with any Lua 5.x:   lua tests/logic_info_test.lua

package.path = "./?.lua;" .. package.path

AccessibilityLevel = { None = 0, Partial = 1, Inspect = 3, SequenceBreak = 5,
                       Normal = 6, Cleared = 7 }
local HELD = {}
Tracker = { ProviderCountForCode = function(_, code) return HELD[code] or 0 end }

-- count writes the way PopTracker's onChange would see them
local writes = 0
-- NB: the fields must live in a backing store, not on the proxy itself.
-- __newindex only fires while the key is ABSENT, so a rawset stub would count
-- the first write to each field and silently miss every one after it.
ScriptHost = {
    CreateLuaItem = function()
        local store = {}
        return setmetatable({}, {
            __index = function(_, k) return store[k] end,
            __newindex = function(_, k, v)
                if k == "BadgeText" or k == "Name" then writes = writes + 1 end
                store[k] = v
            end
        })
    end
}
ImageReference = { FromPackRelativePath = function(_, p) return p end }

require("scripts.logic.rf4_rules")
require("scripts.logic_info")

local fails = 0
local function check(label, cond, extra)
    print(string.format("%-56s %s", label, cond and "PASS" or "FAIL"))
    if not cond then
        fails = fails + 1
        if extra then print("     " .. tostring(extra)) end
    end
end

RF4_Invalidate()
local item = CreateLogicInfoItem()

check("item is created", item ~= nil)
check("PotentialCodes is set and not empty",
      type(item.PotentialCodes) == "table" and #item.PotentialCodes > 0)
check("provides its own code", item.ProvidesCodeFunc(item, LOGIC_INFO_CODE) == 1)
check("does not provide anything else", item.ProvidesCodeFunc(item, "obsidianbridge") == 0)
check("badge counts the yellow checks", tonumber(item.BadgeText) ~= nil, item.BadgeText)
check("tooltip mentions the area-item count",
      item.Name:find("area items %d+/12") ~= nil, item.Name)

-- the loop guard: same state in, no further writes
local before = writes
RF4_UpdateLogicInfo()
RF4_UpdateLogicInfo()
check("repeat updates with unchanged state write nothing", writes == before,
      string.format("%d extra write(s) -- this would re-enter StateChanged", writes - before))

-- a real state change must still push through
HELD = { obsidianbridge = 1 }
RF4_Invalidate()
RF4_UpdateLogicInfo()
check("a changed state does update the item", writes > before)

-- and everything in logic reads as such
local ALL = {}
for _, n in ipairs(RF4_AREA_ITEMS) do ALL[RF4_ITEM_CODE[n]] = 1 end
HELD = ALL
RF4_Invalidate()
RF4_UpdateLogicInfo()
print("     with all 12 area items: " .. item.Name)

print()
print(fails == 0 and string.format("ALL PASS  (0 failures)") or
      string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

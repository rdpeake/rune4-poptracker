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
local FRAME_HANDLERS = {}
ScriptHost = {
    AddOnFrameHandler = function(_, name, fn) FRAME_HANDLERS[name] = fn end,
    RemoveOnFrameHandler = function(_, name) FRAME_HANDLERS[name] = nil end,
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

-- PopTracker aborts a Lua call longer than Tracker::DEFAULT_EXEC_LIMIT =
-- 600000 instructions (tracker.h), and this runs inside the "*" watch, so
-- blowing it kills the update with `Execution aborted. Limit reached.` and the
-- badge silently stops.
local EXEC_LIMIT = 600000

---@return integer approximate VM instructions executed by fn
local function instructions(fn)
    local n = 0
    debug.sethook(function() n = n + 1000 end, "", 1000)
    fn()
    debug.sethook()
    return n
end

local worst, worst_at = 0, "nothing held"
local granted = {}
for i = 0, #RF4_AREA_ITEMS do
    if i > 0 then granted[RF4_ITEM_CODE[RF4_AREA_ITEMS[i]]] = 1 end
    HELD = granted
    RF4_Invalidate()
    local n = instructions(RF4_UpdateLogicInfo)
    if n > worst then
        worst, worst_at = n, i == 0 and "nothing held"
            or string.format("%d area item(s)", i)
    end
end
check(string.format("one update stays inside PopTracker's %d instruction budget",
                    EXEC_LIMIT),
      worst < EXEC_LIMIT,
      string.format("worst was ~%d with %s -- PopTracker would abort StateChanged",
                    worst, worst_at))
print(string.format("     worst update ~%d instructions (%d%% of the budget, with %s)",
                    worst, math.floor(worst * 100 / EXEC_LIMIT), worst_at))

-- Nested watch callbacks accrue against the budget of the call on the stack:
-- ScheduleLocationOptions writes one item per option, and a synchronous sweep
-- per write would spend that handler's single budget several times over.
HELD = ALL
RF4_Invalidate()
RF4_UpdateLogicInfo()
local one_sweep = instructions(function()
    RF4_Invalidate()
    RF4_MarkLogicInfoStale()
    RF4_LogicInfoFrame()
end)

local burst = instructions(function()
    -- ten item changes in one frame handler, as a bulk option apply does
    for _ = 1, 10 do
        RF4_Invalidate()
        RF4_MarkLogicInfoStale()
    end
    RF4_LogicInfoFrame()
end)
check("ten item changes in one call cost one sweep, not ten",
      burst < one_sweep * 2,
      string.format("burst ~%d vs one sweep ~%d", burst, one_sweep))
check("and the burst stays inside the budget", burst < EXEC_LIMIT,
      string.format("~%d of %d", burst, EXEC_LIMIT))
print(string.format("     10 changes + 1 frame ~%d instructions (one sweep ~%d)",
                    burst, one_sweep))

check("a frame with nothing marked does no work",
      instructions(RF4_LogicInfoFrame) < 1000)

-- The deferral only helps if StateChanged actually uses it. Calling
-- RF4_UpdateLogicInfo from there again would restore the pile-up silently,
-- since one sweep on its own still fits the budget.
local function file_contains(path, needle)
    local f = io.open(path, "r")
    if not f then return false end
    local body = f:read("a")
    f:close()
    return body:find(needle, 1, true) ~= nil
end
local STATE_CHANGED = "scripts/logic/graph_logic/logic_main.lua"
check("StateChanged marks the summary stale",
      file_contains(STATE_CHANGED, "RF4_MarkLogicInfoStale"))
check("and does not sweep synchronously",
      not file_contains(STATE_CHANGED, "RF4_UpdateLogicInfo"))

print()
print(fails == 0 and string.format("ALL PASS  (0 failures)") or
      string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

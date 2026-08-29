-- Test for scripts/location_options.lua
--
-- PopTracker has no test runner, so this stubs out the slice of its API the
-- option handler touches (Tracker:FindObjectForCode, the frame handlers,
-- ForceUpdate) and drives the handler through the cases that matter.
--
-- Run from the pack root with any Lua 5.x:   lua tests/location_options_test.lua

package.path = "./?.lua;" .. package.path

local ITEMS, FRAME_HANDLERS, FORCED = {}, {}, 0
local log = {}
local realprint = print
print = function(...) local t={} for i=1,select('#',...) do t[i]=tostring((select(i,...))) end
                     log[#log+1]=table.concat(t," ") end

Tracker = { FindObjectForCode = function(_, code) return ITEMS[code] end }
ScriptHost = {
    AddOnFrameHandler = function(_, name, fn) FRAME_HANDLERS[name] = fn end,
    RemoveOnFrameHandler = function(_, name) FRAME_HANDLERS[name] = nil end,
}
function ForceUpdate() FORCED = FORCED + 1 end
local function pump(n) for _=1,n do
    for name, fn in pairs(FRAME_HANDLERS) do if FRAME_HANDLERS[name] then fn() end end end end

require("scripts.autotracking.option_for_location")
require("scripts.location_options")

local function reset(initial)
    ITEMS, FRAME_HANDLERS, FORCED, log = {}, {}, 0, {}
    for _, c in ipairs(OPTION_CODES) do ITEMS[c] = { Active = initial } end
end
local function snapshot() local t={} for _,c in ipairs(OPTION_CODES) do t[c]=ITEMS[c].Active end return t end
local function count(t, v) local n=0 for _,x in pairs(t) do if x==v then n=n+1 end end return n end

-- build a location pool containing only these option groups
local function poolFor(codes)
    local want = {}; for _, c in ipairs(codes) do want[c] = true end
    local pool = {}
    for id, code in pairs(OPTION_FOR_LOCATION) do
        if want[code] then pool[#pool+1] = id end
    end
    return pool
end

local fails = 0
local function check(label, cond, extra)
    realprint(string.format("%-58s %s", label, cond and "PASS" or "FAIL"))
    if not cond then fails = fails + 1; if extra then realprint("     " .. extra) end end
end

realprint("== T1: user hand-enabled ALL 15; room only has 3 groups ==")
reset(true)                              -- every toggle manually on
SLOT_DATA = {}
ALL_LOCATIONS = poolFor({"opt_cropsanity","opt_dropsanity","opt_tamesanity"})
ScheduleLocationOptions()
pump(29); local mid = snapshot()
check("nothing applied before the delay elapses", count(mid,true) == 15)
pump(1); local after = snapshot()
check("exactly the 3 room groups remain on", count(after,true) == 3)
check("  opt_cropsanity  on",  after.opt_cropsanity  == true)
check("  opt_dropsanity  on",  after.opt_dropsanity  == true)
check("  opt_tamesanity  on",  after.opt_tamesanity  == true)
check("manually-set opt_fishsanity was UNSET", after.opt_fishsanity == false)
check("manually-set opt_spellsanity was UNSET", after.opt_spellsanity == false)
check("ForceUpdate() called", FORCED == 1, "FORCED="..FORCED)
check("frame handler removed after applying", FRAME_HANDLERS["location_options handler"] == nil)
realprint("     log: " .. table.concat(log, " | "))

realprint("\n== T2: not connected (empty pool) -> leave the player's toggles alone ==")
reset(true); ALL_LOCATIONS = {}; log = {}
ApplyLocationOptions(nil)
check("all 15 untouched", count(snapshot(), true) == 15)
check("ForceUpdate() not called", FORCED == 0)

realprint("\n== T3: pool of ids we don't recognise -> refuse to blank everything ==")
reset(true); ALL_LOCATIONS = {9990001, 9990002, 9990003}; log = {}
ApplyLocationOptions(nil)
check("all 15 untouched", count(snapshot(), true) == 15)
check("diagnostic printed", (log[1] or ""):find("did not match") ~= nil
                          or (log[1] or ""):find("matched") ~= nil, log[1])

realprint("\n== T4: user hand-DISABLED everything; room has those groups ==")
reset(false)
ALL_LOCATIONS = poolFor({"opt_forgesanity","opt_dishsanity"})
ApplyLocationOptions(nil)
local t4 = snapshot()
check("opt_forgesanity turned back ON", t4.opt_forgesanity == true)
check("opt_dishsanity  turned back ON", t4.opt_dishsanity == true)
check("only those 2 on", count(t4, true) == 2)

realprint("\n== T5: slot_data Friendsanity=0 with friend locations absent ==")
reset(true)
ALL_LOCATIONS = poolFor({"opt_cropsanity"})
ApplyLocationOptions({ Friendsanity = 0, Tamesanity = 0 })
local t5 = snapshot()
check("opt_friendsanity off", t5.opt_friendsanity == false)
check("opt_tamesanity off", t5.opt_tamesanity == false)
check("opt_cropsanity on", t5.opt_cropsanity == true)

realprint("\n== T6: every group present -> nothing changes, no needless ForceUpdate ==")
reset(true); FORCED = 0
local all = {}; for _, c in ipairs(OPTION_CODES) do all[#all+1] = c end
ALL_LOCATIONS = poolFor(all)
ApplyLocationOptions(nil)
check("all 15 stay on", count(snapshot(), true) == 15)
check("ForceUpdate() skipped when nothing changed", FORCED == 0, "FORCED="..FORCED)

realprint(string.format("\n%s  (%d failure%s)", fails==0 and "ALL PASS" or "FAILURES",
                        fails, fails==1 and "" or "s"))
os.exit(fails == 0 and 0 or 1)

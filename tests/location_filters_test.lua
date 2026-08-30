-- Test for scripts/location_filters.lua.
--
-- Five apworld options decide the location pool and none reach fill_slot_data.
-- Offline the pack's own settings answer for them; connected, the room's id
-- list does, exactly. The interesting cases are the boundaries (shipments are
-- cut at >= the cap, tames and friendship at > it), the refusal to filter on a
-- location list that is not ours, and max_sell_value, which cannot be recovered
-- and must present itself as unknown rather than as a plausible default.
--
-- Run from the pack root with any Lua 5.x:   lua tests/location_filters_test.lua

package.path = "./?.lua;" .. package.path

local HELD = {}
local ITEMS = {}
local function item(code)
    ITEMS[code] = ITEMS[code] or { AcquiredCount = 0, Active = false,
                                   BadgeText = "", MinCount = 0,
                                   IgnoreUserInput = false }
    return ITEMS[code]
end
Tracker = {
    ProviderCountForCode = function(_, code)
        if ITEMS[code] then
            if ITEMS[code].Active then return 1 end
            return ITEMS[code].AcquiredCount
        end
        return HELD[code] or 0
    end,
    FindObjectForCode = function(_, code) return item(code) end,
}
function print_stub() end

require("scripts.logic.rf4_data")     -- RF4_LOC, for the sanity check
require("scripts.location_filters")

local fails = 0
local function check(label, want, got)
    local ok = want == got
    print(string.format("%-58s %s", label, ok and "PASS" or
          string.format("FAIL (want %s, got %s)", tostring(want), tostring(got))))
    if not ok then fails = fails + 1 end
end

-- pick representative ids out of the generated metadata
local function anyWith(meta, want)
    local best
    for id, v in pairs(meta) do
        if v == want and (best == nil or id < best) then best = id end
    end
    return best
end
local ship_t9  = anyWith(RF4_SHIP_TIER, 9)
local ship_t8  = anyWith(RF4_SHIP_TIER, 8)
local tame_t9  = anyWith(RF4_TAME_TIER, 9)
local tame_t10 = anyWith(RF4_TAME_TIER, 10)
local friend6  = anyWith(RF4_FRIEND_TIER, 6)
local friend7  = anyWith(RF4_FRIEND_TIER, 7)

-- == offline: the pack's own settings answer ==============================
print("\n== offline, defaults (max tier 9, max friend 6) ==")
SLOT_LOCATIONS = nil
ITEMS = {}
item("opt_maxshiptier").AcquiredCount = 9
item("opt_maxfriend").AcquiredCount = 6
item("opt_maxsell").AcquiredCount = 500   -- thousands; 500000 G
item("opt_grocerysanity").Active = true
item("opt_outfitsanity").Active = false

check("shipment at tier 8 visible (cut is >=)", 1, RF4Visible(ship_t8))
check("shipment at tier 9 hidden  (cut is >=)", 0, RF4Visible(ship_t9))
check("tame at tier 9 visible     (cut is >)",  1, RF4Visible(tame_t9))
check("tame at tier 10 hidden     (cut is >)",  0, RF4Visible(tame_t10))
check("friendship level 6 visible (cut is >)",  1, RF4Visible(friend6))
check("friendship level 7 hidden  (cut is >)",  0, RF4Visible(friend7))
check("grocery shown when the toggle is on", 1, RF4Visible(next(RF4_GROCERY_LOC)))

-- The item stores THOUSANDS, because six digits overflow a 32px badge and
-- cover the items beside it. 500 in the item must mean 500000 G in the filter.
local cheap, dear = nil, nil
for id, sell in pairs(RF4_SHIP_SELL) do
    if sell < 500000 and (cheap == nil or sell > RF4_SHIP_SELL[cheap]) then cheap = id end
    if sell >= 500000 and (dear == nil or sell < RF4_SHIP_SELL[dear]) then dear = id end
end
if cheap and dear then
    check(string.format("sells for %d, under the 500000 cap -> shown",
          RF4_SHIP_SELL[cheap]), 1, RF4Visible(cheap))
    check(string.format("sells for %d, at or over it -> hidden",
          RF4_SHIP_SELL[dear]), 0, RF4Visible(dear))
else
    print("  (no shipment straddles the default cap; scale not exercised)")
end
check("outfit hidden when the toggle is off", 0, RF4Visible(next(RF4_OUTFIT_LOC)))

item("opt_grocerysanity").Active = false
check("grocery hidden when the toggle is off", 0, RF4Visible(next(RF4_GROCERY_LOC)))

-- == connected: the room's list wins, whatever the settings say ============
print("\n== connected ==")
-- a room that kept tiers 1..8 and friendship 1..6, i.e. the defaults
ALL_LOCATIONS = {}
for id in pairs(RF4_LOC) do
    local keep = true
    local t = RF4_SHIP_TIER[id];   if t and t >= 9 then keep = false end
    local tt = RF4_TAME_TIER[id];  if tt and tt > 9 then keep = false end
    local f = RF4_FRIEND_TIER[id]; if f and f > 6 then keep = false end
    if keep then ALL_LOCATIONS[#ALL_LOCATIONS + 1] = id end
end
check("slot list accepted", true, BuildSlotLocations())

-- settings deliberately set wrong; the room must override them
item("opt_maxshiptier").AcquiredCount = 5
item("opt_grocerysanity").Active = false
check("tier 8 visible because the room has it", 1, RF4Visible(ship_t8))
check("tier 9 hidden because the room lacks it", 0, RF4Visible(ship_t9))
check("grocery visible despite the toggle being off", 1,
      RF4Visible(next(RF4_GROCERY_LOC)))

local applied, unknown = ApplyRoomToPanel()
check("two values recovered from the room", 2, applied)
check("one value undetermined", 1, unknown)
check("max ship tier read back as 9", 9, item("opt_maxshiptier").AcquiredCount)
check("max friend read back as 6", 6, item("opt_maxfriend").AcquiredCount)
check("max ship tier locked", true, item("opt_maxshiptier").IgnoreUserInput)

-- the one that cannot be recovered must say so, not show a default
check("max sell blanked to 0 (greys the consumable)", 0,
      item("opt_maxsell").AcquiredCount)
check("max sell badged '?'", "?", item("opt_maxsell").BadgeText)
check("max sell locked too", true, item("opt_maxsell").IgnoreUserInput)

-- == a location list that is not ours must not blank the tracker ===========
print("\n== foreign location list ==")
ALL_LOCATIONS = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 }
check("refuses to filter", false, BuildSlotLocations())
check("SLOT_LOCATIONS cleared", nil, SLOT_LOCATIONS)
-- falls back to the pack's settings rather than hiding everything; tier is 9
-- again after ApplyRoomToPanel, so tier 8 shows and tier 9 does not
check("falls back to settings, not to blank", 1, RF4Visible(ship_t8))
check("and still applies them", 0, RF4Visible(ship_t9))

-- == offline again hands the settings back =================================
print("\n== back offline ==")
ALL_LOCATIONS = {}
BuildSlotLocations()
ApplyRoomToPanel()
check("max ship tier unlocked", false, item("opt_maxshiptier").IgnoreUserInput)
check("max sell unlocked", false, item("opt_maxsell").IgnoreUserInput)

print()
print(fails == 0 and "ALL PASS  (0 failures)" or string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

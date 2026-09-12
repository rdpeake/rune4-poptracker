-- The apworld options that decide which locations a slot contains but never
-- reach fill_slot_data, so the pack cannot simply be told:
--
--   max_ship_tier   shipments, chests and tames with tier above it, and
--                   barriers, boxes and searches whose REGION's tier is
--                   above it
--   max_sell_value  shipments with sell value >= it
--   max_friendship  friendship levels above it
--
-- grocerysanity and outfitsanity DO arrive in slot_data, but their tables are
-- here too: offline there is no slot to ask.
--
-- Each is a pack setting for planning offline. On connect ALL_LOCATIONS is
-- every id in the slot, so RF4Visible simply asks whether an id is in it.
--
-- Inference exists only to fill the settings panel back in. Where a value
-- cannot be recovered the setting is greyed and badged "?" -- see InferFromRoom.

require("scripts.autotracking.location_meta")

-- The four tables max_ship_tier caps. A barrier, box or search is capped by
-- its REGION's tier rather than its own, and a region the apworld's
-- region_tiers does not name is absent from the table and never cut: Sand
-- Pond's boxes, Keeno Lake's search.
local TIER_CAPPED = { RF4_SHIP_TIER, RF4_CHEST_TIER, RF4_TAME_TIER, RF4_REGION_TIER }

-- `scale` is the multiplier between what the item stores and what the apworld
-- compares against. max_sell_value runs 10000..800000 in whole 10k steps, and
-- six digits overflow a 32px item badge and cover its neighbours, so the item
-- holds thousands and this scales it back up.
VALUE_OPTIONS = {
    opt_maxshiptier = { default = 9,   min = 5,  max = 11 },
    opt_maxfriend   = { default = 6,   min = 1,  max = 10 },
    opt_maxsell     = { default = 500, min = 10, max = 800, scale = 1000 },
}

---every location id in the connected slot, or nil when not connected
SLOT_LOCATIONS = nil

local function count(code)
    return Tracker:ProviderCountForCode(code)
end

---a value setting's current number, falling back to the apworld default when
---the item is missing or has been blanked to mark it undetermined
---@param code string
---@return integer
local function value(code)
    local n = count(code)
    local spec = VALUE_OPTIONS[code]
    local scale = (spec and spec.scale) or 1
    if spec and (n == nil or n < spec.min) then return spec.default * scale end
    return n * scale
end

---PopTracker visibility rule: "$RF4Visible|<ap location id>"
---No "^" prefix -- visibility resolves through the count branch, which wants 0/1.
---@param apid string|number
---@return integer
function RF4Visible(apid)
    local id = tonumber(apid)
    if id == nil then return 1 end

    if SLOT_LOCATIONS ~= nil then
        return SLOT_LOCATIONS[id] and 1 or 0
    end

    -- offline: answer from the pack's own settings
    if RF4_ABSENT[id] then return 0 end
    if RF4_GROCERY_LOC[id] and count("opt_grocerysanity") == 0 then return 0 end
    if RF4_OUTFIT_LOC[id] and count("opt_outfitsanity") == 0 then return 0 end

    -- every cut-off is exclusive: a tier equal to the cap is kept
    for _, tiers in ipairs(TIER_CAPPED) do
        local tier = tiers[id]
        if tier and tier > value("opt_maxshiptier") then return 0 end
    end

    local s = RF4_SHIP_SELL[id]
    if s and s >= value("opt_maxsell") then return 0 end
    local f = RF4_FRIEND_TIER[id]
    if f and f > value("opt_maxfriend") then return 0 end

    return 1
end

---Lowest cut-off consistent with which of `meta`'s locations survived.
---A cap is believable only if every level at or above it is gone and every
---level below it kept something; a thinned level was cut by another option.
---Every cut-off is exclusive (level > cap is dropped), so the lowest missing
---level is one above the cap.
---@param meta table<integer, integer>  location id -> level
---@return integer|nil cap, boolean confident
local function inferCap(meta)
    local total, present = {}, {}
    for id, lvl in pairs(meta) do
        total[lvl] = (total[lvl] or 0) + 1
        if SLOT_LOCATIONS[id] then present[lvl] = (present[lvl] or 0) + 1 end
    end
    local levels = {}
    for lvl in pairs(total) do levels[#levels + 1] = lvl end
    table.sort(levels)

    local first_gone = nil
    for _, lvl in ipairs(levels) do
        local kept = present[lvl] or 0
        if kept == 0 then
            if first_gone == nil then first_gone = lvl end
        elseif first_gone ~= nil then
            return nil, false      -- a surviving level above a dead one: not a cap
        end
    end
    if first_gone == nil then return nil, false end   -- nothing cut at all
    return first_gone - 1, true
end

---What did the room choose? Fills the settings panel back in.
---@return table<string, table>  code -> {value=?, confident=bool, note=string}
function InferFromRoom()
    local out = {}
    if SLOT_LOCATIONS == nil then return out end

    local tier, ok = inferCap(RF4_SHIP_TIER)
    out.opt_maxshiptier = { value = tier, confident = ok,
        note = ok and "from the room" or "no tier is cleanly absent" }

    -- friendship only exists as locations when friendsanity is set to them;
    -- with it off every level is gone and the cap is unknowable, not zero.
    local any_friend = false
    for id in pairs(RF4_FRIEND_TIER) do
        if SLOT_LOCATIONS[id] then any_friend = true break end
    end
    if any_friend then
        local lvl, fok = inferCap(RF4_FRIEND_TIER)
        out.opt_maxfriend = { value = lvl, confident = fok,
            note = fok and "from the room" or "levels are not cleanly capped" }
    else
        out.opt_maxfriend = { value = nil, confident = false,
            note = "friendsanity is not set to locations" }
    end

    -- max_sell_value is continuous, and the room bounds it rather than fixing
    -- it, so it is always reported as undetermined. Shipments the tier cap
    -- already explains are skipped: counting them would make the bound
    -- meaningless.
    local tier_cap = (out.opt_maxshiptier.confident and out.opt_maxshiptier.value) or nil
    local hi_kept, lo_cut = nil, nil
    for id, sell in pairs(RF4_SHIP_SELL) do
        local t = RF4_SHIP_TIER[id]
        -- matches the cut: a tier equal to the cap is kept, so the cap does
        -- not explain it away
        local explained = tier_cap ~= nil and t ~= nil and t > tier_cap
        if not explained then
            if SLOT_LOCATIONS[id] then
                if hi_kept == nil or sell > hi_kept then hi_kept = sell end
            elseif lo_cut == nil or sell < lo_cut then
                lo_cut = sell
            end
        end
    end
    local note
    if hi_kept and lo_cut and lo_cut > hi_kept then
        note = string.format("somewhere in %d..%d", hi_kept + 1, lo_cut)
    elseif hi_kept and lo_cut == nil then
        note = string.format("nothing was cut by price, so it is above %d", hi_kept)
    else
        note = "cannot be bounded from the room"
    end
    out.opt_maxsell = { value = nil, confident = false, note = note }

    return out
end

-- Applying the room ----------------------------------------------------------

---Build the slot's id set from ALL_LOCATIONS.
---Refuses ids that do not look like this game's: SLOT_LOCATIONS drives
---RF4Visible, so a foreign or stale list would blank the tracker entirely.
---@return boolean built
function BuildSlotLocations()
    if ALL_LOCATIONS == nil or #ALL_LOCATIONS == 0 then
        SLOT_LOCATIONS = nil
        return false
    end
    local set, known, n = {}, 0, 0
    for _, id in ipairs(ALL_LOCATIONS) do
        local num = tonumber(id)
        if num then
            n = n + 1
            -- dropped here rather than in RF4Visible, so the slot's list is
            -- right for everything that reads it and the check costs one probe
            -- per connect instead of one per section per refresh
            if not RF4_ABSENT[num] then set[num] = true end
            if RF4_LOC == nil or RF4_LOC[num] ~= nil then known = known + 1 end
        end
    end
    if n == 0 or known * 2 < n then
        print(string.format(
            "location_filters: only %d of %d location ids are ours, not filtering",
            known, n))
        SLOT_LOCATIONS = nil
        return false
    end
    SLOT_LOCATIONS = set
    return true
end

---@param meta table<integer, integer>
---@return boolean
local function anyPresent(meta)
    for id in pairs(meta) do
        if SLOT_LOCATIONS[id] then return true end
    end
    return false
end

---Push what the room chose onto the settings panel.
---A value the room fixed is set and locked. One the room only bounds is blanked
---to zero -- PopTracker greys a consumable at zero -- badged "?" and locked.
---@return integer applied, integer undetermined
function ApplyRoomToPanel()
    local applied, undetermined = 0, 0

    if SLOT_LOCATIONS == nil then
        -- offline: hand every value setting back to the player
        for code, spec in pairs(VALUE_OPTIONS) do
            local obj = Tracker:FindObjectForCode(code)
            if obj ~= nil then
                obj.IgnoreUserInput = false
                obj.MinCount = spec.min
                obj.BadgeText = ""
                if obj.AcquiredCount < spec.min then obj.AcquiredCount = spec.default end
            end
        end
        return 0, 0
    end

    -- The two category toggles infer exactly, like the other fifteen -- but
    -- only where the slot did not say outright, which it now does for both.
    -- Guessing "no grocery locations survived, so grocerysanity is off" is
    -- wrong for a slot that cut them all on tier or sell value instead.
    local given = SLOT_GIVEN_OPTIONS or {}
    for code, meta in pairs({ opt_grocerysanity = RF4_GROCERY_LOC,
                              opt_outfitsanity  = RF4_OUTFIT_LOC }) do
        local obj = Tracker:FindObjectForCode(code)
        if obj ~= nil and not given[code] then obj.Active = anyPresent(meta) end
    end

    local inferred = InferFromRoom()
    for code, spec in pairs(VALUE_OPTIONS) do
        local obj = Tracker:FindObjectForCode(code)
        local r = inferred[code]
        if obj ~= nil and r ~= nil then
            if r.confident and r.value then
                obj.MinCount = spec.min
                obj.AcquiredCount = r.value
                obj.BadgeText = tostring(r.value)
                applied = applied + 1
            else
                obj.MinCount = 0
                obj.AcquiredCount = 0
                obj.BadgeText = "?"
                undetermined = undetermined + 1
            end
            -- either way the room, not the player, owns it now
            obj.IgnoreUserInput = true
            print(string.format("location_filters: %s %s (%s)", code,
                  r.value and tostring(r.value) or "undetermined", r.note))
        end
    end
    return applied, undetermined
end

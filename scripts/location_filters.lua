-- The five apworld options that decide which locations a slot contains but
-- never reach fill_slot_data, so the pack cannot simply be told:
--
--   grocerysanity   Product/Grocery/Fruit/Bread/Tool shipments
--   outfitsanity    outfit locations
--   max_ship_tier   shipments with tier >= it, and tames with tier > it
--   max_sell_value  shipments with sell value >= it
--   max_friendship  friendship levels above it
--
-- Each is a pack setting the player can set by hand for planning offline. On
-- connect the room itself is the authority, and it is exact where inference is
-- not: ALL_LOCATIONS is every id in the slot, so RF4Visible can simply ask
-- whether an id is in it. That covers all five at once, plus the category
-- toggles and the locations the apworld drops outright.
--
-- Inference only exists to fill the SETTINGS PANEL back in, so the numbers the
-- room chose are visible rather than merely obeyed. Where a value cannot be
-- recovered the setting is greyed and badged "?" instead of showing a guess --
-- see InferFromRoom for which of them that is and why.

require("scripts.autotracking.location_meta")

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
---Note: no "^" prefix. Visibility is a boolean, and resolveRules is called for
---visibility rules with the count branch, which is what 0/1 wants.
---@param apid string|number
---@return integer
function RF4Visible(apid)
    local id = tonumber(apid)
    if id == nil then return 1 end

    if SLOT_LOCATIONS ~= nil then
        return SLOT_LOCATIONS[id] and 1 or 0
    end

    -- offline: answer from the pack's own settings
    if RF4_GROCERY_LOC[id] and count("opt_grocerysanity") == 0 then return 0 end
    if RF4_OUTFIT_LOC[id] and count("opt_outfitsanity") == 0 then return 0 end

    local maxtier = value("opt_maxshiptier")
    local t = RF4_SHIP_TIER[id]
    if t and t >= maxtier then return 0 end          -- shipments use >=
    local tt = RF4_TAME_TIER[id]
    if tt and tt > maxtier then return 0 end         -- tames use >

    local s = RF4_SHIP_SELL[id]
    if s and s >= value("opt_maxsell") then return 0 end
    local f = RF4_FRIEND_TIER[id]
    if f and f > value("opt_maxfriend") then return 0 end

    return 1
end

---Lowest cut-off consistent with which of `meta`'s locations survived.
---Returns the boundary and whether it is trustworthy: a cap is only believable
---if every level at or above it is entirely gone AND every level below it kept
---something. A level that is merely thinned was cut by a different option.
---@param meta table<integer, integer>  location id -> level
---@param inclusive boolean  true when the apworld drops level >= cap
---@return integer|nil cap, boolean confident
local function inferCap(meta, inclusive)
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
    return (inclusive and first_gone or first_gone - 1), true
end

---What did the room choose? Fills the settings panel back in.
---@return table<string, table>  code -> {value=?, confident=bool, note=string}
function InferFromRoom()
    local out = {}
    if SLOT_LOCATIONS == nil then return out end

    local tier, ok = inferCap(RF4_SHIP_TIER, true)
    out.opt_maxshiptier = { value = tier, confident = ok,
        note = ok and "from the room" or "no tier is cleanly absent" }

    -- friendship only exists as locations when friendsanity is set to them;
    -- with it off every level is gone and the cap is unknowable, not zero.
    local any_friend = false
    for id in pairs(RF4_FRIEND_TIER) do
        if SLOT_LOCATIONS[id] then any_friend = true break end
    end
    if any_friend then
        local lvl, fok = inferCap(RF4_FRIEND_TIER, false)
        out.opt_maxfriend = { value = lvl, confident = fok,
            note = fok and "from the room" or "levels are not cleanly capped" }
    else
        out.opt_maxfriend = { value = nil, confident = false,
            note = "friendsanity is not set to locations" }
    end

    -- max_sell_value is continuous: 380 distinct values over a 10k..800k range,
    -- and only 2 shipments are cut at the default. The room bounds it rather
    -- than fixing it, so this one is always reported as undetermined.
    -- A shipment can be missing because of the tier cap rather than its price,
    -- and counting those makes the bound meaningless (the cheapest tier-10 item
    -- would "prove" the cap is 1). Skip anything the tier cap already explains,
    -- and only report a bound that is actually coherent.
    local tier_cap = (out.opt_maxshiptier.confident and out.opt_maxshiptier.value) or nil
    local hi_kept, lo_cut = nil, nil
    for id, sell in pairs(RF4_SHIP_SELL) do
        local t = RF4_SHIP_TIER[id]
        local explained = tier_cap ~= nil and t ~= nil and t >= tier_cap
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
---Refuses when the ids do not look like this game's. SLOT_LOCATIONS drives
---RF4Visible, so accepting a foreign or stale list would blank the tracker
---entirely -- the same reasoning as OptionsFromRoom's "leaving options alone".
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
            set[num] = true
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
---A value the room fixed is set and locked. One the room only bounds is
---blanked to zero -- PopTracker greys a consumable at zero -- badged "?" and
---locked, so the panel reads "the room decided this and I cannot recover it"
---rather than showing a stale default that looks authoritative.
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

    -- the two category toggles infer exactly, like the other fifteen
    for code, meta in pairs({ opt_grocerysanity = RF4_GROCERY_LOC,
                              opt_outfitsanity  = RF4_OUTFIT_LOC }) do
        local obj = Tracker:FindObjectForCode(code)
        if obj ~= nil then obj.Active = anyPresent(meta) end
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

-- Location options
--
-- The apworld has a "sanity" toggle for each group of locations a slot may
-- contain, but fill_slot_data sends only some of them. So each is a pack
-- toggle the player can set by hand, and on connect we correct them from the
-- room itself.
--
-- ALL_LOCATIONS (built in PreOnClear from MissingLocations + CheckedLocations)
-- is every location id in the slot. That is exact and covers every option,
-- including the ones that never reach slot_data.
--
-- This runs from OnFrameHandler rather than the end of OnClear: the clear
-- handler fires before PopTracker has finished settling item state, so options
-- set there can be overwritten.

-- OPTION_CODES -- every option that gates a location -- is generated into
-- scripts/autotracking/option_for_location.lua beside the table it indexes,
-- so an option the apworld adds cannot be missing from one and present in the
-- other. (opt_searchsanity was, while the list was kept by hand here.)

---@return table<string, boolean> OPTION_CODES as a set
local function knownCodes()
    local set = {}
    for _, code in ipairs(OPTION_CODES) do set[code] = true end
    return set
end

---@param code string
---@param on boolean
---@return boolean changed
local function setOption(code, on)
    local obj = Tracker:FindObjectForCode(code)
    if obj == nil then
        print("location_options: no item for " .. code)
        return false
    end
    local want = on and true or false
    if obj.Active == want then return false end
    obj.Active = want
    return true
end

---which options does the connected slot actually use?
---@return table<string, boolean>|nil nil when we have no location list yet
function OptionsFromRoom()
    if ALL_LOCATIONS == nil or #ALL_LOCATIONS == 0 then
        return nil
    end
    local used = knownCodes()
    for code in pairs(used) do used[code] = false end
    local gated = 0
    for _, id in ipairs(ALL_LOCATIONS) do
        local code = OPTION_FOR_LOCATION[id]
        if code then
            used[code] = true
            gated = gated + 1
        end
    end
    if gated == 0 then
        -- every id was unknown to us: wrong game, or the map is stale.
        -- Do not blank every option on that basis.
        print("location_options: none of " .. #ALL_LOCATIONS ..
              " location ids matched OPTION_FOR_LOCATION, leaving options alone")
        return nil
    end
    return used
end

---apply slot_data, then correct from the room's own location list
---@param slot_data table|nil
function ApplyLocationOptions(slot_data)
    if slot_data then
        -- The 2026-09-04 apworld sends five more of these than it used to, so
        -- they no longer have to be inferred from the room's location list.
        -- The pack's code for an option is "opt_" .. the apworld's own name
        -- lowercased, which is what fill_slot_data keys them by -- so match on
        -- that rather than on a table of names, and an option upstream adds or
        -- recapitalises (Friendsanity vs ChestSanity) arrives on its own.
        local known = knownCodes()
        for key, value in pairs(slot_data) do
            local code = "opt_" .. string.lower(tostring(key))
            if known[code] and (type(value) == "number" or type(value) == "boolean") then
                setOption(code, value ~= 0 and value ~= false)
            end
        end
    end
    -- The five options that never reach slot_data are handled separately; see
    -- scripts/location_filters.lua. Guarded because this module is loaded on
    -- its own by tests/location_options_test.lua.
    local built, fixed, unknown = false, 0, 0
    if BuildSlotLocations then
        built = BuildSlotLocations()
        fixed, unknown = ApplyRoomToPanel()
    end
    if built then
        print(string.format(
            "location_filters: %d value settings taken from the room, %d undetermined",
            fixed, unknown))
    end

    local used = OptionsFromRoom()
    if used == nil then
        if built then ForceUpdate() end
        return
    end
    local on, off, changed = 0, 0, 0
    for _, code in ipairs(OPTION_CODES) do
        if setOption(code, used[code]) then changed = changed + 1 end
        if used[code] then on = on + 1 else off = off + 1 end
    end
    print(string.format(
        "location_options: %d groups in this slot, %d hidden, %d toggles changed",
        on, off, changed))
    if changed > 0 or built then
        ForceUpdate()
    end
end

-- Deferred apply -------------------------------------------------------------
--
-- OnClear fires before PopTracker has finished restoring the saved state for
-- the room's seed, so options set from inside it get overwritten by whatever
-- the player had toggled by hand. Wait a few frames, then apply once.

local APPLY_DELAY_FRAMES = 30
local frames_left = 0

local function OnOptionFrame()
    frames_left = frames_left - 1
    if frames_left > 0 then return end
    ScriptHost:RemoveOnFrameHandler("location_options handler")
    ApplyLocationOptions(SLOT_DATA)
end

---called from OnClear; applies the options once the clear has settled
function ScheduleLocationOptions()
    frames_left = APPLY_DELAY_FRAMES
    ScriptHost:AddOnFrameHandler("location_options handler", OnOptionFrame)
end

-- Location options
--
-- The apworld has 15 "sanity" toggles deciding which location groups a slot
-- contains, but fill_slot_data only sends Friendsanity and Tamesanity. So each
-- is a pack toggle the player can set by hand, and on connect we correct them
-- from the room itself.
--
-- ALL_LOCATIONS (built in PreOnClear from MissingLocations + CheckedLocations)
-- is every location id in the slot. That is exact and covers all 15 options,
-- including the 13 that never reach slot_data.
--
-- This runs from OnFrameHandler rather than the end of OnClear: the clear
-- handler fires before PopTracker has finished settling item state, so options
-- set there can be overwritten.

OPTION_CODES = {
    "opt_cropsanity", "opt_fishsanity", "opt_goldcropsanity", "opt_largecropsanity",
    "opt_dropsanity", "opt_craftsanity", "opt_forgesanity", "opt_dishsanity",
    "opt_spellsanity", "opt_foragesanity", "opt_chemicsanity", "opt_mineralsanity",
    "opt_requestsanity", "opt_friendsanity", "opt_tamesanity",
}

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
    local used = {}
    for _, code in ipairs(OPTION_CODES) do used[code] = false end
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
        if slot_data["Friendsanity"] ~= nil then
            setOption("opt_friendsanity", slot_data["Friendsanity"] ~= 0)
        end
        if slot_data["Tamesanity"] ~= nil then
            setOption("opt_tamesanity", slot_data["Tamesanity"] ~= 0)
        end
    end
    local used = OptionsFromRoom()
    if used == nil then
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
    if changed > 0 then
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

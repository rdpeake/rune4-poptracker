-- Follow the player around the maps: the RF4 client reports which room the
-- player is in, and this switches the map tab to match.
--
-- Tracker:UiHint("ActivateTab", <name>) is PopTracker's only handle on tabs.
-- Every tabbed container receives it and applies it if it holds a tab of that
-- name, ignoring it otherwise, so a nested tab is reached by sending the path
-- outermost first: "Autumn Road", "Leon Karnak", "Rune Prana", "F3".
--
-- Modelled on https://github.com/vyneras/pokemon-frlg-tracker

require("scripts.autotracking.tab_mapping")

AUTO_TAB_CODE = "opt_autotab"

-- Fields that may carry the room, best first, compared case-insensitively.
-- The client sends currentMap; the rest cover older and renamed builds.
RF4_MAP_KEYS = { "currentmap", "current_map", "mapupdate", "map_update",
                 "mapid", "map_id", "roomid", "room_id", "room",
                 "playerlocation", "location" }

-- widest the badge shows at overlay_font_size 9 without spilling over its
-- neighbours
BADGE_MAX_CHARS = 6

-- packets described in full before going quiet
RF4_LOG_LIMIT = 20

local logged = 0
local badge_item = nil
local showing_path = nil   -- tab path on screen; the "already there" test
local last_raw = nil       -- last value received, as received
local last_reported = nil
local warned = {}

---@param fmt string
local function log(fmt, ...)
    if logged >= RF4_LOG_LIMIT then return end
    logged = logged + 1
    print("auto_tab: " .. string.format(fmt, ...))
    if logged == RF4_LOG_LIMIT then
        print(string.format("auto_tab: %d packets logged; going quiet."
            .. " Set RF4_LOG_LIMIT higher and reconnect for more.", RF4_LOG_LIMIT))
    end
end

---Is the log still open? Lua evaluates arguments eagerly, so a log line whose
---arguments cost something to build has to be guarded at the call site or it
---goes on being built for the whole session after log() has gone quiet.
---@return boolean
local function logging()
    return logged < RF4_LOG_LIMIT
end

---one line of a table's keys and values, so an unrecognised packet still says
---what it carries and the real field name can be read off the log
---@param t any
---@return string
local function describe(t)
    if type(t) ~= "table" then return tostring(t) end
    local keys = {}
    for k, v in pairs(t) do
        keys[#keys + 1] = string.format("%s=%s", tostring(k),
            type(v) == "table" and "{...}" or tostring(v))
    end
    table.sort(keys)
    return #keys > 0 and table.concat(keys, " ") or "(empty)"
end

local function navigation_enabled()
    return Tracker:ProviderCountForCode(AUTO_TAB_CODE) > 0
end

-- == the button ==========================================================

---Put a value on the auto-navigate button, whatever it is.
---
---Unconditional by design: this readout is how rooms get classified, so it must
---not depend on the value parsing or on navigation being on.
---@param value any
function RF4_ShowMapValue(value)
    last_raw = value ~= nil and tostring(value) or nil
    local text = last_raw or ""
    if #text > BADGE_MAX_CHARS then
        text = text:sub(1, BADGE_MAX_CHARS - 1) .. "\u{2026}"   -- log keeps it whole
    end
    if badge_item == nil then
        badge_item = Tracker:FindObjectForCode(AUTO_TAB_CODE)
        if badge_item == nil then
            log("cannot find the %s item to badge", AUTO_TAB_CODE)
            return
        end
    end
    if badge_item.BadgeText ~= text then
        badge_item.BadgeText = text
    end
end

-- == navigation ==========================================================

---Switch to the tab for a room id, if it is not already showing. Needs the
---option on, a numeric id and a known tab path; anything else is dropped.
---@param mapId integer|string|nil
---@return boolean navigated
function RF4_UpdateMap(mapId)
    if not navigation_enabled() then return false end
    local id = tonumber(mapId)
    if id == nil then
        log("room %s is not a number, so nothing to navigate to", tostring(mapId))
        return false
    end
    if RF4_ROOM_HOLD and RF4_ROOM_HOLD[id] then
        -- An interior: the pack has no map for one, so hold what is showing
        -- rather than jump to the town. showing_path is left alone, so stepping
        -- back outside sends nothing either.
        if not warned[id] then
            warned[id] = true
            log("room %d (%s) is an interior; holding the current map",
                id, RF4_ROOM_NAME[id] or "unknown")
        end
        return false
    end
    local tabs = RF4_TAB_MAPPING[id]
    if tabs == nil then
        -- The game draws this room on no minimap the pack has a map for, so
        -- there is nowhere to navigate to. Said once, with the id the player
        -- can read back off the badge.
        if not warned[id] then
            warned[id] = true
            log("room %d (%s) is on no map the pack draws -- nothing to"
                .. " navigate to", id, RF4_ROOM_NAME[id] or "unknown")
        end
        return false
    end
    local path = table.concat(tabs, " > ")
    if path == showing_path then return false end
    showing_path = path
    log("room %d (%s) -> %s", id, RF4_ROOM_NAME[id] or "unknown", path)
    for _, tab in ipairs(tabs) do
        Tracker:UiHint("ActivateTab", tab)
    end
    return true
end

-- == packets =============================================================

---Find a map field in one table, case-insensitively.
---@param t any
---@return any value, string? key
local function find_map_value(t)
    if type(t) ~= "table" then return nil, nil end
    local lower = {}
    for k, v in pairs(t) do
        if type(k) == "string" then lower[k:lower()] = { k, v } end
    end
    for _, want in ipairs(RF4_MAP_KEYS) do
        local hit = lower[want]
        if hit ~= nil and type(hit[2]) ~= "table" then return hit[2], hit[1] end
    end
    return nil, nil
end

---Archipelago Bounced handler. The payload normally sits under `data`, but the
---top level is checked too rather than insisting on a shape the client has not
---settled on yet.
---@param json table
function RF4_OnBounced(json)
    if type(json) ~= "table" then
        log("bounced something that is not a table: %s", tostring(json))
        return
    end
    local data = json["data"]
    local value, key = find_map_value(data)
    local where = "data"
    if value == nil then
        value, key = find_map_value(json)
        where = "packet"
    end
    if value == nil then
        -- naming every field of both levels means the real one can be read off
        -- this line and added to RF4_MAP_KEYS. describe() walks and sorts a
        -- table, and this branch runs on EVERY bounce packet once the field is
        -- renamed away, so it is built only while the log is still open.
        if logging() then
            log("bounce with no map field -- data: %s -- packet: %s",
                describe(data), describe(json))
        end
        return
    end
    log("map field %s.%s = %s", where, key, tostring(value))
    RF4_ShowMapValue(value)
    RF4_UpdateMap(value)
end

---Look for a room in slot_data on connect. Only ever sets the opening tab.
---@param slot_data table|nil
function RF4_MapFromSlotData(slot_data)
    local value, key = find_map_value(slot_data)
    if value == nil then
        if logging() then
            log("connected; slot_data has no map field -- keys: %s", describe(slot_data))
        end
        return
    end
    log("slot_data carries a room in %s", key)
    RF4_ShowMapValue(value)
    RF4_UpdateMap(value)
end

---forget everything, so the next report navigates and badges afresh
function RF4_ResetMap()
    showing_path = nil
    last_reported = nil
    warned = {}
    logged = 0
    RF4_ShowMapValue(nil)
end

---How many rooms the generated table knows about.
---@return integer
function RF4_MappedRoomCount()
    local n = 0
    for _ in pairs(RF4_TAB_MAPPING) do n = n + 1 end
    return n
end

---One line, on connect and on every toggle, saying whether navigation is armed
---and whether anything has arrived. It is the only output that needs no
---incoming packet, so without it "no log output" cannot be told apart from
---"this build has no auto_tab in it at all".
function RF4_ReportAutoTabState()
    local on = navigation_enabled()
    -- Writing the badge emits onChange on this item, re-entering the watch that
    -- calls this; acting only on a real change makes that second pass a no-op.
    if on == last_reported then return end
    last_reported = on
    print(string.format(
        "auto_tab: ready -- option %s, %d rooms mapped, last value seen: %s",
        on and "ON" or "OFF (the badge still updates; nothing will navigate)",
        RF4_MappedRoomCount(),
        last_raw or "none yet -- nothing has been received from the client"))
end

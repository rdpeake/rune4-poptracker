-- Access logic ported from the Rune Factory 4 apworld.
--
-- scripts/logic/rf4_data.lua is generated from the apworld source and holds the
-- region graph, the entrance rules, the recipe/shipment tables and one AND-list
-- of clauses per AP location id. This file evaluates them.
--
-- Clause forms (mirroring Rules.py):
--   {"R", region}      region is reachable
--   {"T", n}           has n area items          can_reach_tier
--   {"C", recipe}      can_make_recipe
--   {"G", item}        can_get_item              recipe, else shipment tier+region
--   {"H", item[, n]}   state.has
--   {"S", key}         Rune Sphere >= the named option
--   {"L"}              has_licenses
--   {"TT"} / {"MT"}    can_make_top_tool / can_make_mid_tool
--   {"P", pct}         ship_percent
--   {"O", {clauses}}   any of

require("scripts.logic.rf4_data")

-- Runesphere counts come from slot data; these are the apworld's defaults and
-- are overwritten on connect by RF4_SetOptions.
RF4_OPT = { fortress = 4, runeprana = 4 }

local LEVEL_ITEM = {
    Crafting  = "Crafting Level Up",
    Cooking   = "Cooking Level Up",
    Forging   = "Forging Level Up",
    Chemistry = "Chemistry Level Up",
}

local reach_cache   = nil   -- region name -> true
local item_cache    = {}    -- can_get_item memo
local recipe_cache  = {}    -- can_make_recipe memo
local busy          = {}    -- recursion guard for cyclic ingredient chains

---drop every cached result; called whenever tracked items change
function RF4_Invalidate()
    reach_cache  = nil
    item_cache   = {}
    recipe_cache = {}
    busy         = {}
end

local function count(name)
    local code = RF4_ITEM_CODE[name]
    if not code then return 0 end
    return Tracker:ProviderCountForCode(code)
end

---state.has_from_list(area_items, player, n)
local function tier_count()
    local n = 0
    for _, name in ipairs(RF4_AREA_ITEMS) do
        n = n + count(name)
    end
    return n
end

local eval_clauses, can_get_item, can_make_recipe, reachable

---@return boolean
function can_make_recipe(name)
    local cached = recipe_cache[name]
    if cached ~= nil then return cached end
    local d = RF4_RECIPES[name]
    if not d then return false end
    if busy[name] then return false end          -- ingredient cycle
    busy[name] = true

    local level, craft, ingredients = d[1], d[2], d[3]
    local ok = false
    local level_item = LEVEL_ITEM[craft]
    if level_item and count(level_item) >= level then
        ok = true
        for _, ingredient in ipairs(ingredients) do
            if not can_get_item(ingredient) then ok = false break end
        end
    end

    busy[name] = nil
    recipe_cache[name] = ok
    return ok
end

---@return boolean
function can_get_item(name)
    local cached = item_cache[name]
    if cached ~= nil then return cached end
    local ok
    if RF4_RECIPES[name] then
        ok = can_make_recipe(name)
    else
        local d = RF4_SHIPMENTS[name]
        if d then
            ok = tier_count() >= d[1] and reachable(d[2])
        else
            ok = false                            -- apworld logs "Can't get item"
        end
    end
    item_cache[name] = ok
    return ok
end

---fraction of shipment regions reachable, as the apworld computes it
local function ship_percent(pct)
    local n = 0
    for _, d in pairs(RF4_SHIPMENTS) do
        if reachable(d[2]) then n = n + 1 end
    end
    return (n / RF4_TOTAL_SHIPMENTS) * 100 >= pct
end

local function has_licenses()
    return count("Forging License") >= 1 and count("Crafting License") >= 1
end

local function can_make_top_tool()
    return count("Forging License") >= 1 and count("Forging Level Up") >= 19
        and can_get_item("Platinum")
end

local function can_make_mid_tool()
    return count("Forging License") >= 1 and count("Forging Level Up") >= 6
        and can_get_item("Silver")
end

---@return boolean
local function eval_clause(c)
    local k = c[1]
    if     k == "R"  then return reachable(c[2])
    elseif k == "T"  then return tier_count() >= c[2]
    elseif k == "C"  then return can_make_recipe(c[2])
    elseif k == "G"  then return can_get_item(c[2])
    elseif k == "H"  then return count(c[2]) >= (c[3] or 1)
    elseif k == "S"  then
        local need = type(c[2]) == "number" and c[2] or (RF4_OPT[c[2]] or 4)
        return count("Rune Sphere") >= need
    elseif k == "L"  then return has_licenses()
    elseif k == "TT" then return can_make_top_tool()
    elseif k == "MT" then return can_make_mid_tool()
    elseif k == "P"  then return ship_percent(c[2])
    elseif k == "O"  then
        for _, sub in ipairs(c[2]) do
            if eval_clause(sub) then return true end
        end
        return false
    end
    return false
end

---@return boolean
function eval_clauses(clauses)
    for _, c in ipairs(clauses) do
        if not eval_clause(c) then return false end
    end
    return true
end

---Region reachability.
---Entrance rules can themselves ask whether a region is reachable (a request
---that needs a shippable item, say), so this is a monotone fixpoint: sweep the
---graph until a pass adds nothing. The memo caches are cleared each sweep
---because their results depend on the reachable set as it stood.
local function compute_reach()
    local r = { ["Menu"] = true }
    reach_cache = r
    local changed = true
    while changed do
        changed = false
        item_cache, recipe_cache, busy = {}, {}, {}
        for from, exits in pairs(RF4_EXITS) do
            if r[from] then
                for _, to in ipairs(exits) do
                    if not r[to] then
                        local rule = RF4_ENTRANCE[from .. " -> " .. to]
                        if rule == nil or eval_clauses(rule) then
                            r[to] = true
                            changed = true
                        end
                    end
                end
            end
        end
    end
    return r
end

---@return boolean
function reachable(region)
    if reach_cache == nil then compute_reach() end
    return reach_cache[region] == true
end

---apply the runesphere requirements from the connected slot
---@param slot_data table|nil
function RF4_SetOptions(slot_data)
    if not slot_data then return end
    RF4_OPT.fortress  = tonumber(slot_data["fortress_runespheres"])  or RF4_OPT.fortress
    RF4_OPT.runeprana = tonumber(slot_data["runeprana_runespheres"]) or RF4_OPT.runeprana
    RF4_Invalidate()
end

---PopTracker access rule: "$RF4Access|<ap location id>"
---@param apid string
---@return accessibilityLevel
function RF4Access(apid)
    local clauses = RF4_LOC[tonumber(apid)]
    if clauses == nil then return AccessibilityLevel.Normal end
    if eval_clauses(clauses) then return AccessibilityLevel.Normal end
    return AccessibilityLevel.None
end

---PopTracker access rule for a whole region: "$RF4Region|<region name>"
---@param region string
---@return accessibilityLevel
function RF4Region(region)
    if reachable(region) then return AccessibilityLevel.Normal end
    return AccessibilityLevel.None
end

-- Exposed for tests/rf4_logic_test.lua, which diffs these against the
-- apworld's own Python implementations.
RF4 = {
    reachable       = reachable,
    can_get_item    = can_get_item,
    can_make_recipe = can_make_recipe,
    eval_clauses    = eval_clauses,
    tier_count      = tier_count,
}

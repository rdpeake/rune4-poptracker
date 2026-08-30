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

local reach_cache   = nil   -- region name -> true, in logic
local loose_cache   = nil   -- region name -> true, physically standable
local item_cache    = {}    -- can_get_item memo
local recipe_cache  = {}    -- can_make_recipe memo
local busy          = {}    -- recursion guard for cyclic ingredient chains

---drop every cached result; called whenever tracked items change
function RF4_Invalidate()
    reach_cache  = nil
    loose_cache  = nil
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

---Entrance clause kinds that gate physical access rather than logic.
---
---"H" is an unlock item by construction -- the apworld puts the region behind
---holding it (the bridges, Etherlink, Volkanon Axe, the licences that ARE the
---Forge/Crafting/Chemistry rooms, Magic Shop, Clothing Shop). That is a wider
---set than RF4_AREA_ITEMS, which is only the list can_reach_tier counts, so
---membership of that list is the wrong test. "S" is Rune Spheres, the story
---items that open the Floating Empire, Rune Prana and the Sharance Maze.
---
---Everything else on an entrance is a logic gate, not a wall:
---  "G"              can you obtain this
---  "T"              are you carrying enough area items yet
---  "P"/"TT"/"MT"    shipment rate, top/mid tool
---  "L"              has_licenses. You do not need a forging licence to cross
---                   a bridge; the apworld hangs it on four entrances as a
---                   proxy for "gear up before you go in", and each of those
---                   four also names a real unlock item, so relaxing it keeps
---                   the wall and drops only the crafting requirement.
local ENTRANCE_ACCESS = { H = true, S = true }

---Physical reachability: the region graph with only the access clauses on each
---entrance required. This answers "could I stand here?" rather than "does the
---seed expect me to be here?", and is what separates a red check from a yellow
---one. Access clauses are plain item counts -- no entrance rule contains an "R"
---clause -- so unlike compute_reach this recurses into nothing and needs no
---memo sweep.
local function compute_loose()
    local r = { ["Menu"] = true }
    loose_cache = r
    local changed = true
    while changed do
        changed = false
        for from, exits in pairs(RF4_EXITS) do
            if r[from] then
                for _, to in ipairs(exits) do
                    if not r[to] then
                        local rule = RF4_ENTRANCE[from .. " -> " .. to]
                        local ok = true
                        if rule then
                            for _, c in ipairs(rule) do
                                if ENTRANCE_ACCESS[c[1]] and not eval_clause(c) then
                                    ok = false
                                    break
                                end
                            end
                        end
                        if ok then
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
local function loosely_reachable(region)
    if loose_cache == nil then compute_loose() end
    return loose_cache[region] == true
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
---
---Three states rather than two. A location's clauses divide into the {"R"}
---region clauses, which say whether you can physically stand in front of the
---check, and everything else, which says whether the seed considers it in
---logic -- the crafting chains, the area-item count, the key items.
---
---  region unreachable        -> None           red
---  reachable, out of logic   -> SequenceBreak  yellow
---  reachable and in logic    -> Normal         green
---
---Yellow is PopTracker's "glitches required" state; it survives the
---"hide unreachable locations" filter, so these stay on the map.
---@param apid string
---@return accessibilityLevel
function RF4Access(apid)
    local clauses = RF4_LOC[tonumber(apid)]
    if clauses == nil then return AccessibilityLevel.Normal end
    local out_of_logic = false
    for _, c in ipairs(clauses) do
        if not eval_clause(c) then
            -- eval_clause answers an "R" clause with the STRICT fixpoint, which
            -- fails a region whose entrance merely needs something crafted. Ask
            -- the relaxed graph before calling it red.
            if c[1] == "R" and not loosely_reachable(c[2]) then
                return AccessibilityLevel.None
            end
            out_of_logic = true
        end
    end
    if out_of_logic then return AccessibilityLevel.SequenceBreak end
    return AccessibilityLevel.Normal
end

---------------------------------------------------------------- why is it yellow
-- PopTracker cannot put dynamic text on a location section: LocationSection
-- exposes only AvailableChestCount, CapturedItem and Highlight to Lua
-- (locationsection.cpp Lua_NewIndex), and the tooltip renders the section's
-- static JSON name. So these build the strings and scripts/logic_info.lua
-- surfaces them on a hoverable item instead.

---one clause as a phrase, e.g. "9 area items (have 1)"
---@param c table
---@return string
local function clause_text(c)
    local k = c[1]
    if k == "T"  then return string.format("%d area items (have %d)", c[2], tier_count()) end
    if k == "C"  then return "to craft " .. c[2] end
    if k == "G"  then return "to obtain " .. c[2] end
    if k == "H"  then
        local n = c[3] or 1
        if n > 1 then return string.format("%d x %s", n, c[2]) end
        return c[2]
    end
    if k == "S"  then
        local need = type(c[2]) == "number" and c[2] or (RF4_OPT[c[2]] or 4)
        return string.format("%d Rune Spheres (have %d)", need, count("Rune Sphere"))
    end
    if k == "L"  then return "the Forging and Crafting licences" end
    if k == "TT" then return "a top-tier tool" end
    if k == "MT" then return "a mid-tier tool" end
    if k == "P"  then return string.format("a %d%% shipment rate", c[2]) end
    if k == "R"  then return c[2] .. " to be in logic" end
    if k == "O"  then
        local parts = {}
        for _, sub in ipairs(c[2]) do parts[#parts+1] = clause_text(sub) end
        return "either " .. table.concat(parts, " or ")
    end
    return k
end

---What is holding `region` out of logic, given you can already stand in it?
---A region can have several ways in; this names the first blocked entrance
---whose source side is already standable, which is the one a player is most
---likely looking at.
---@param region string
---@return string|nil
local function region_block(region)
    for from, exits in pairs(RF4_EXITS) do
        if loosely_reachable(from) then
            for _, to in ipairs(exits) do
                if to == region then
                    local rule = RF4_ENTRANCE[from .. " -> " .. to]
                    if rule then
                        local parts = {}
                        for _, c in ipairs(rule) do
                            if not eval_clause(c) then parts[#parts+1] = clause_text(c) end
                        end
                        if #parts > 0 then return table.concat(parts, " and ") end
                    end
                end
            end
        end
    end
    return nil
end

---Why is this location not green? Empty string when it is in logic.
---@param apid string|number
---@return string
function RF4Why(apid)
    local clauses = RF4_LOC[tonumber(apid)]
    if clauses == nil then return "" end
    local missing = {}
    for _, c in ipairs(clauses) do
        if not eval_clause(c) then
            if c[1] == "R" then
                if not loosely_reachable(c[2]) then
                    return "Out of reach: cannot get to " .. c[2]
                end
                local blocked = region_block(c[2])
                missing[#missing+1] = blocked
                    and (c[2] .. " needs " .. blocked)
                    or  (c[2] .. " is out of logic")
            else
                missing[#missing+1] = clause_text(c)
            end
        end
    end
    if #missing == 0 then return "" end
    return "Out of logic: needs " .. table.concat(missing, "; ")
end

---Categories a yellow check can be blocked on, for the summary item.
local CATEGORY = {
    T = "area items", C = "crafting", G = "gathering", H = "key items",
    O = "key items", L = "licences", S = "Rune Spheres",
    TT = "tools", MT = "tools", P = "shipment rate", R = "regions",
}
local CATEGORY_ORDER = { "area items", "regions", "crafting", "gathering",
                         "key items", "licences", "Rune Spheres", "tools",
                         "shipment rate" }

---Counts for the hoverable summary: how many checks are out of logic, and on
---what. A check blocked on two things is counted under both.
---@return integer, table<string, integer>
function RF4LogicSummary()
    local yellow, by = 0, {}
    for apid, clauses in pairs(RF4_LOC) do
        if RF4Access(tostring(apid)) == AccessibilityLevel.SequenceBreak then
            yellow = yellow + 1
            local seen = {}
            for _, c in ipairs(clauses) do
                if not eval_clause(c) then
                    local cat = CATEGORY[c[1]]
                    if cat and not seen[cat] then
                        seen[cat] = true
                        by[cat] = (by[cat] or 0) + 1
                    end
                end
            end
        end
    end
    return yellow, by
end

---The summary as one line, for a tooltip.
---@return string
function RF4LogicSummaryText()
    local yellow, by = RF4LogicSummary()
    if yellow == 0 then
        return "Every reachable check is in logic."
    end
    local parts = {}
    for _, cat in ipairs(CATEGORY_ORDER) do
        if by[cat] then parts[#parts+1] = string.format("%s %d", cat, by[cat]) end
    end
    return string.format("%d checks reachable but out of logic  --  %s  (area items %d/%d)",
                         yellow, table.concat(parts, ", "), tier_count(), #RF4_AREA_ITEMS)
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
    loosely_reachable = loosely_reachable,
    region_block      = region_block,
    tier_count      = tier_count,
}

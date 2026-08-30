-- A hoverable summary of what is holding checks out of logic.
--
-- PopTracker has no way to put dynamic text on a location section: from Lua a
-- LocationSection exposes only AvailableChestCount, CapturedItem and Highlight
-- (locationsection.cpp Lua_NewIndex), and the map tooltip renders the section's
-- static JSON name (maptooltip.cpp). A LuaItem, though, has a live Name -- shown
-- as its tooltip -- and a live BadgeText, so the per-check reasons from
-- RF4Why() are surfaced here instead: the badge counts the yellow checks, the
-- tooltip breaks them down, and a left click dumps every one with its reason to
-- the log.

LOGIC_INFO_CODE = "rf4_logic_info"

local item = nil
local last_badge, last_name

---push the current summary onto the item. Guarded on equality: assigning
---BadgeText/Name emits onChange, which is what StateChanged watches, so an
---unconditional write here would feed itself.
function RF4_UpdateLogicInfo()
    if not item then return end
    local yellow = RF4LogicSummary()
    local badge = yellow > 0 and tostring(yellow) or ""
    local name = RF4LogicSummaryText()
    if badge ~= last_badge then
        last_badge = badge
        item.BadgeText = badge
    end
    if name ~= last_name then
        last_name = name
        item.Name = name
    end
end

---dump every out-of-logic check and why, to the log
local function DumpLogicReasons()
    local ids = {}
    for apid in pairs(RF4_LOC) do ids[#ids + 1] = apid end
    table.sort(ids)
    print("--- Rune Factory 4: checks reachable but out of logic ---")
    print(RF4LogicSummaryText())
    local n = 0
    for _, apid in ipairs(ids) do
        if RF4Access(tostring(apid)) == AccessibilityLevel.SequenceBreak then
            n = n + 1
            print(string.format("  %d  %s", apid, RF4Why(apid)))
        end
    end
    print(string.format("--- %d out of logic ---", n))
    return true
end

---@return LuaItem
function CreateLogicInfoItem()
    local self = ScriptHost:CreateLuaItem()
    self.Name = "Logic"
    self.Icon = ImageReference:FromPackRelativePath("/images/items/close.png")
    -- PopTracker treats PotentialCodes as authoritative once set; see
    -- scripts/luaitems.lua for the trap this avoids.
    self.PotentialCodes = { LOGIC_INFO_CODE }
    self.CanProvideCodeFunc = function(_, code) return code == LOGIC_INFO_CODE end
    -- provide the code so the item renders enabled; no access rule uses it
    self.ProvidesCodeFunc = function(_, code) return code == LOGIC_INFO_CODE and 1 or 0 end
    self.OnLeftClickFunc = DumpLogicReasons
    item = self
    RF4_UpdateLogicInfo()
    return self
end

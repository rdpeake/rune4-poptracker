-- Show the Requests tab only when the seed has request checks.
--
-- PopTracker has no visibility rule for a tab, so the panel is swapped whole:
-- item_panel.json and item_panel_requests.json define the same two keys and
-- whichever loads last wins. Re-calling AddLayouts at runtime is how the
-- Pokemon FRLG tracker switches its own layout variants.

REQUEST_OPTION = "opt_requestsanity"

local showing = nil

---@param on boolean whether the Requests tab should be present
local function apply(on)
    if on == showing then return end
    showing = on
    if on then
        Tracker:AddLayouts("layouts/item_panel_requests.json")
    else
        Tracker:AddLayouts("layouts/item_panel.json")
    end
end

---Match the panel to the requestsanity option. Safe to call at any time.
function RF4_UpdateItemPanel()
    apply(Tracker:ProviderCountForCode(REQUEST_OPTION) > 0)
end

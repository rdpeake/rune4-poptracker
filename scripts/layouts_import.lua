Tracker:AddLayouts("layouts/settings_popup.json")
Tracker:AddLayouts("layouts/events.json")
Tracker:AddLayouts("layouts/items.json")
Tracker:AddLayouts("layouts/tabs.json")
Tracker:AddLayouts("layouts/item_panel.json")
Tracker:AddLayouts("layouts/tracker.json")
Tracker:AddLayouts("layouts/broadcast.json")

-- Items Only draws the same panels with nothing beside them.
--
-- Each tracker_* root is a background around one tracker_body_* key, so the
-- variant and the chroma swap (scripts/chroma.lua) never write to the same
-- key: items_only.json redefines the bodies, chroma_on/off redefine the
-- roots, and either can load after the other.
if Tracker.ActiveVariantUID == "Items Only" then
    Tracker:AddLayouts("layouts/items_only.json")
end

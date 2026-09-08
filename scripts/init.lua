-- Items
require("scripts.items_import")

-- Logic
require("scripts.logic.logic_helper")
require("scripts.logic.base_logic")
require("scripts.logic.graph_logic.logic_main")
-- access logic ported from the apworld (rf4_data.lua is generated)
require("scripts.logic.request_events")
require("scripts.logic.rf4_rules")
require("scripts.logic_info")
require("scripts.location_filters")
require("scripts.item_panel")
require("scripts.chroma")
require("scripts.auto_tab")

-- Maps
Tracker:AddMaps("maps/maps.json")

-- Layout
require("scripts.layouts_import")

-- Locations
require("scripts.locations_import")

-- AutoTracking for PopTracker
if PopVersion and PopVersion >= "0.26.0" then
    require("scripts.autotracking")
end

function OnFrameHandler()
    ScriptHost:RemoveOnFrameHandler("load handler")
    -- stuff
    ScriptHost:AddWatchForCode("StateChanged", "*", StateChanged)
    ScriptHost:AddOnLocationSectionChangedHandler("location_section_change_handler", LocationHandler)
    -- the Requests tab is present only when the seed has request checks
    ScriptHost:AddWatchForCode("requests tab", REQUEST_OPTION, RF4_UpdateItemPanel)
    RF4_UpdateItemPanel()
    -- flat background for chroma keying; see scripts/chroma.lua
    ScriptHost:AddWatchForCode("chroma background", CHROMA_OPTION, RF4_UpdateChroma)
    RF4_UpdateChroma()
    if RF4_ReportAutoTabState then
        ScriptHost:AddWatchForCode("auto tab option", AUTO_TAB_CODE,
                                   RF4_ReportAutoTabState)
        RF4_ReportAutoTabState()
    end
    CreateLuaManualStorageItem("manual_location_storage")
    CreateLogicInfoItem()
    ForceUpdate()
end
require("scripts.luaitems")
require("scripts.watches")
ScriptHost:AddOnFrameHandler("load handler", OnFrameHandler)
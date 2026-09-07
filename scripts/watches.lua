Archipelago:AddClearHandler("clear handler", OnClear)
Archipelago:AddItemHandler("item handler", OnItem)
Archipelago:AddLocationHandler("location handler", OnLocation)

Archipelago:AddSetReplyHandler("notify handler", OnNotify)
Archipelago:AddRetrievedHandler("notify launch handler", OnNotifyLaunch)
-- Follows the player around the maps; see scripts/auto_tab.lua. The result is
-- printed because AddBouncedHandler returns false silently when the callback is
-- nil or there is no connection yet, which looks identical from the outside to
-- a session where no bounce ever arrives.
if Archipelago:AddBouncedHandler("bounce handler", RF4_OnBounced) then
    print("auto_tab: bounce handler registered")
else
    print("auto_tab: FAILED to register the bounce handler"
        .. " -- auto-navigation cannot work this session")
end
-- ScriptHost:AddWatchForCode("settings autofill handler", "autofill_settings", AutoFill)
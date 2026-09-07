-- Swap one of two layout files in, driven by an option code.
--
-- PopTracker has no visibility rule for a tab or for a background, so the
-- thing is swapped whole: the two files define the same keys and whichever
-- loads last wins. Re-calling AddLayouts at runtime is how the Pokemon FRLG
-- tracker switches its own layout variants.
--
-- AddLayouts re-reads and re-parses the file and rebuilds the view, so a swap
-- that changes nothing is worth skipping. `off_json` is always a file
-- scripts/layouts_import.lua has already loaded, which is why `showing` starts
-- false rather than nil: with the option off -- the default -- the first call
-- is a no-op instead of a second, identical load.

---@param code string the option code to follow
---@param on_json string layout to load when the option is set
---@param off_json string layout to load when it is not; the imported default
---@return function updater matches the layout to the option; safe to call any time
function RF4_LayoutSwap(code, on_json, off_json)
    local showing = false
    return function()
        local on = Tracker:ProviderCountForCode(code) > 0
        if on == showing then return end
        showing = on
        Tracker:AddLayouts(on and on_json or off_json)
    end
end

-- A flat, keyable background, for streaming the tracker over a scene.
--
-- The pack paints its root containers transparent, so PopTracker's own dark
-- window shows through and a chroma key would take the pack's darkest art with
-- it. This repaints those roots one flat colour instead, swapped the way the
-- Requests tab is (scripts/item_panel.lua): chroma_on.json and chroma_off.json
-- define the same three roots and whichever loads last wins.
--
-- Magenta, being the colour the pack's artwork stays furthest from -- much
-- further than green or cyan, which the maps and item tiles both come close to.

require("scripts.layout_swap")

CHROMA_OPTION = "opt_chroma"

---Match the background to the option. Safe to call at any time.
RF4_UpdateChroma = RF4_LayoutSwap(CHROMA_OPTION,
                                  "layouts/chroma_on.json",
                                  "layouts/chroma_off.json")

-- Show the Requests tab only when the seed has request checks.
--
-- item_panel.json and item_panel_requests.json define the same two keys and
-- whichever loads last wins; scripts/layout_swap.lua does the swapping.

require("scripts.layout_swap")

REQUEST_OPTION = "opt_requestsanity"

---Match the panel to the requestsanity option. Safe to call at any time.
RF4_UpdateItemPanel = RF4_LayoutSwap(REQUEST_OPTION,
                                     "layouts/item_panel_requests.json",
                                     "layouts/item_panel.json")

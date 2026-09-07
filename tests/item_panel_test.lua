-- Test for scripts/item_panel.lua, the Requests tab.
--
-- PopTracker has no visibility rule for a tab, so the whole panel is swapped:
-- two layout files define the same keys and the last loaded wins. Worth
-- pinning: the variant with the tab loads only when requestsanity is on, and a
-- redundant swap is skipped, since AddLayouts rebuilds the whole panel.
--
-- Run from the pack root with any Lua 5.x:   lua tests/item_panel_test.lua

package.path = "./?.lua;" .. package.path

local LOADED = {}
local ON = 0
Tracker = {
    ProviderCountForCode = function(_, code)
        return code == "opt_requestsanity" and ON or 0
    end,
    AddLayouts = function(_, f) LOADED[#LOADED + 1] = f end,
}
require("scripts.item_panel")

local fails = 0
local function check(label, want, got)
    local ok = want == got
    print(string.format("%-56s %s", label, ok and "PASS" or
        string.format("FAIL (want %s, got %s)", tostring(want), tostring(got))))
    if not ok then fails = fails + 1 end
end
local function last() return LOADED[#LOADED] end

ON = 0
RF4_UpdateItemPanel()
check("off: loads the panel without the tab", "layouts/item_panel.json", last())

local n = #LOADED
RF4_UpdateItemPanel()
RF4_UpdateItemPanel()
check("off twice more: no redundant rebuild", n, #LOADED)

ON = 1
RF4_UpdateItemPanel()
check("on: loads the variant with the tab", "layouts/item_panel_requests.json", last())

n = #LOADED
RF4_UpdateItemPanel()
check("on twice: no redundant rebuild", n, #LOADED)

ON = 0
RF4_UpdateItemPanel()
check("back off: swaps the tab away again", "layouts/item_panel.json", last())

-- The whole panel is tabbed, so the options and the pinned locations are
-- repeated INSIDE each tab rather than sitting outside them -- both are worth
-- having while working through the request chain. Counting occurrences is the
-- point: one of each would mean they live on only one tab.
local function panel_bodies(path)
    local f = assert(io.open(path, "r")); local body = f:read("a"); f:close()
    return body
end
local req = panel_bodies("layouts/item_panel_requests.json")
local function occurrences(hay, needle)
    local n, from = 0, 1
    while true do
        local i = hay:find(needle, from, true)
        if not i then return n end
        n = n + 1; from = i + 1
    end
end
-- two layouts (vertical and horizontal) x two tabs each
check("options appear on every tab", 4, occurrences(req, "Location Options / Logic"))
check("pinned locations appear on every tab", 4, occurrences(req, "Pinned Locations"))
-- and the wide grid is used where there is room for it
check("the horizontal panel uses the wide grid", true,
      req:find("event_grid_horizontal", 1, true) ~= nil)
local ev = panel_bodies("layouts/events.json")
check("both grid shapes exist", true,
      ev:find('"event_grid"', 1, true) ~= nil and
      ev:find('"event_grid_horizontal"', 1, true) ~= nil)

-- Each grid has to fit the fixed box it is drawn in, and very nearly fill it:
-- too wide and the last column is clipped once the group's padding counts, too
-- narrow and the group header runs on past the icons.
local BOX = { event_grid = {408, 748}, event_grid_horizontal = {1020, 306} }
for key, box in pairs(BOX) do
    local body = ev:match('"' .. key .. '".-"rows": %[(.-)%]%s*}')
    local grid = ev:match('"' .. key .. '":.-"item_size": "(%d+)')
    local margin = ev:match('"' .. key .. '":.-"item_margin": "(%d+)')
    local cell = tonumber(grid) + 2 * tonumber(margin)
    local widest, rows = 0, 0
    for row in body:gmatch("%[(.-)%]") do
        rows = rows + 1
        local n = 0
        for _ in row:gmatch('"') do n = n + 1 end
        n = n / 2
        if n > widest then widest = n end
    end
    local w, h = widest * cell, rows * cell
    check(key .. " fits its box", true, w <= box[1] and h <= box[2])
    check(key .. " fills the width", true, w >= box[1] - 20)
end

-- The grid slot is a fixed size in every tab, so the options and pinned
-- locations land in the same place whichever tab shows.
--
-- The size MUST be on a canvas, not a group: trackerview.cpp sizes a group to
-- its children and ignores width/height, while canvas pins size/min/max.
local function sizes(path)
    local f = assert(io.open(path, "r")); local body = f:read("a"); f:close()
    local out = {}
    for kind, w, h in body:gmatch('"type": "(%a+)",%s*"width": (%d+),%s*"height": (%d+)') do
        out[#out + 1] = kind .. ":" .. w .. "x" .. h
    end
    return out
end
local s = sizes("layouts/item_panel_requests.json")
check("every tab pins its grid slot", 4, #s)
local all_canvas = true
for _, v in ipairs(s) do
    if v:sub(1, 7) ~= "canvas:" then all_canvas = false end
end
check("and every one is a canvas, not a group", true, all_canvas)
check("both vertical tabs match", true, s[1] == s[2])
check("both horizontal tabs match", true, s[3] == s[4])
local plain = sizes("layouts/item_panel.json")
check("the no-tab panel pins it too", 2, #plain)
check("and to the same sizes", true, plain[1] == s[1] and plain[2] == s[3])

-- both files must define the same keys, or a swap would leave a dangling
-- layout reference and the panel would render empty
local function keys(path)
    local f = assert(io.open(path, "r")); local body = f:read("a"); f:close()
    local out = {}
    for k in body:gmatch('"(item_panel_%a+)"%s*:') do out[k] = true end
    return out
end
local a, b = keys("layouts/item_panel.json"), keys("layouts/item_panel_requests.json")
local same = true
for k in pairs(a) do if not b[k] then same = false end end
for k in pairs(b) do if not a[k] then same = false end end
check("both layout files define the same panel keys", true, same)
check("and there are two of them", 2, (function()
    local n = 0; for _ in pairs(a) do n = n + 1 end; return n end)())

print()
print(fails == 0 and "ALL PASS  (0 failures)" or string.format("FAILURES (%d)", fails))
os.exit(fails == 0 and 0 or 1)

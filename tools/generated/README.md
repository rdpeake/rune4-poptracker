# Generated

Nothing in this folder is edited by hand. Each file is the whole output of one
tool, rewritten from scratch on every run, so an edit here is lost the next time
that tool is used.

    room_positions.json   map -> label -> x,y      | tools/gamedata/derive_rooms.py
    room_extents.json     map -> label -> w,h      |   from rooms.json and the
    room_pins.json        map id -> where its pin  |   game's own minimap table
                          goes
    room_shown.json       map -> the labels drawn  |

    map_layout.json       where each texture is drawn on its pack image
                          tools/gamedata/map_art.py, fitted from the
                          arrangement in tools/map_art.json

    map_objects.json      map id -> the chests, barriers, boxes and search
                          points the game puts in that room
                          tools/gamedata/export_map_objects.py
    check_rooms.json      ap id -> the map ids its object is in, joined on the
                          field flag.  tools/apworld/export_check_rooms.py
    transitions.json      source map -> destination map -> the rooms you
                          leave from.  tools/gamedata/export_transitions.py

They are committed so the rest of the tools run without a copy of the game or
the apworld. To change what is in them, change what they are derived from:
`tools/rooms.json` for the rooms, `tools/map_art.json` for the map
arrangement and captions.

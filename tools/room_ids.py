"""Room id -> map resource name: the table the client's room numbers index.

Committed as `tools/room_ids.json` so the tools run without the game. It came
out of `g_mapResourceTable` in live debuggee memory, each entry dereferenced
through the archive TOC -- not something reproducible from files on disk, which
is why the table is kept rather than re-derived.

875 entries, ids up to 958; an id with no entry is a null slot in the original
table. The save file's playerLocation.room (file +0x2C, u16) indexes it.
_SUMMER/_AUTUMN/_WINTER entries are Map_LoadById's seasonal swap and the
unsuffixed entry is spring.
"""
import json
import os

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
TABLE = PACK + 'tools/room_ids.json'


def room_names():
    """{map id: MAP_* resource name}"""
    with open(TABLE, encoding='utf-8') as fh:
        return {int(i): name for i, name in json.load(fh).items()}


if __name__ == '__main__':
    names = room_names()
    print('%d entries, ids 0..%d' % (len(names), max(names)))

"""Make the Rune Factory 4 apworld importable, however it was obtained.

Put one of these in `tools/apworld/_input/`, which is gitignored:

    rf4.apworld     the file Archipelago ships -- a zip with rf4/ inside
    rf4/            an unpacked checkout of the same thing

A checkout has one trap: `parse_csv` splits on the repr of "\r\n", so a CSV
saved with bare LF yields no rows at all and every table comes back empty. git
on Linux checks them out that way. Convert data/*.csv to CRLF after cloning.

Either works: Python imports straight out of the zip, and the apworld reads its
own CSVs through `pkgutil`, which reads out of a zip too. Nothing else is
needed -- the handful of Archipelago classes the apworld imports are stubbed in
`_stubs/`, which is committed, so the apworld is the only thing to supply.

`_stubs/` also holds pymem, psutil and NetUtils, which are not Archipelago's.
Importing `rf4.Locations` runs `rf4/__init__.py`, and that reaches the PC
client -- the module that reads the running game's memory -- through `.Save`,
so a table the pack only wants to read pulls in a Windows-only dependency.
Stubbing beats installing: nothing in those modules is ever called here.

    from load import apworld
    ap = apworld()
    ap.Locations.location_data_table
    ap.data('barrier_flags')                     # a json under data/
    ap.csv_text('Rune Factory 4 AP - Chests')    # a CSV under data/
"""
import csv
import glob
import importlib
import io
import json
import os
import pkgutil
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE)) + '/'
INPUT = os.path.join(HERE, '_input')

HELP = """No apworld found in tools/apworld/_input/.

Put either of these there:
    rf4.apworld     the file Archipelago ships
    rf4/            an unpacked copy of it

Nothing else is required; the Archipelago stubs it needs are already committed
in tools/apworld/_stubs/."""


def source():
    """The path to put on sys.path: the input folder, or the .apworld itself."""
    if os.path.isdir(os.path.join(INPUT, 'rf4')):
        return INPUT
    for pattern in ('*.apworld', '*.zip'):
        found = sorted(glob.glob(os.path.join(INPUT, pattern)))
        if found:
            return found[0]
    raise SystemExit(HELP)


def apworld():
    """Import the apworld and hand back its modules, plus a data() reader."""
    for path in (os.path.join(HERE, '_stubs'), source()):
        if path not in sys.path:
            sys.path.insert(0, path)
    ap = types.SimpleNamespace()
    for name in ('Locations', 'Items', 'Regions', 'Rules', 'Options', 'game_data'):
        try:
            setattr(ap, name, importlib.import_module('rf4.' + name))
        except ImportError as exc:
            # Loudly. This used to hand back None, and nothing checks for it,
            # so a missing dependency surfaced as an AttributeError on NoneType
            # in whichever exporter touched it first -- or worse, as a table
            # read through getattr() coming back empty and exporting as "no
            # rows", which reads exactly like success.
            raise SystemExit(
                'rf4.%s will not import: %s\nIf that is a third-party module '
                'the apworld needs only for its client, stub it in '
                'tools/apworld/_stubs/ the way pymem and psutil are.'
                % (name, exc))
    _retype_search(ap)
    ap.data = data
    ap.csv_text = csv_text
    ap.resource = resource
    return ap


def _retype_search(ap):
    """TEMPORARY. Give the searchsanity locations their own loc_type.

    Locations.py builds them with a copy of the box block, `loc_type= "box"`, so
    all 28 come back typed as boxes and cannot be told from the 214 real ones.
    Corrected here rather than in each tool, and only here, so it goes away in
    one edit when upstream fixes the line. Reported upstream; not a pack rule.
    """
    L = getattr(ap, 'Locations', None)
    table = getattr(L, 'search_data_table', None)
    if not table:
        return
    for name in table:
        entry = L.location_data_table.get(name)
        if entry is not None and entry.loc_type == 'box':
            L.location_data_table[name] = entry._replace(loc_type='search')


def map_kinds(ap):
    """The loc_types that are an object placed in a room, discovered not listed.

    Such a kind has its own <kind>_data_table whose entries carry a field_flag,
    which is what ties them to the game's own map objects. Nothing here names
    barrier, box or search, so a kind the apworld adds is picked up on its own.
    """
    L = ap.Locations
    kinds = {d.loc_type for d in L.location_data_table.values()
             if d.address is not None}
    out = []
    for kind in sorted(kinds):
        table = getattr(L, kind + '_data_table', None)
        if table and any(hasattr(d, 'field_flag') for d in table.values()):
            out.append(kind)
    return out


def resource(relpath):
    """Bytes of a file inside the apworld package, zip or not."""
    raw = pkgutil.get_data('rf4', relpath)
    if raw is None:
        raise SystemExit('the apworld has no %s' % relpath)
    return raw


def data(name):
    """A json from the apworld's own data/ folder."""
    return json.loads(resource('data/%s.json' % name).decode('utf-8'))


def csv_text(name):
    """One of the apworld's data/ CSVs as text."""
    return resource('data/%s.csv' % name).decode('utf-8-sig')


def csv_rows(name, strip_slashes=False, by_name=False):
    """Rows of one apworld sheet, keyed the way the apworld keys them.

    `name` is the sheet's own name; the "Rune Factory 4 AP - " prefix is added
    here so no caller has to spell it.

    parse_csv does `csvdata[cell["Name"]] = ...`, so where a sheet holds two
    rows with the same Name the later one silently wins and the earlier is
    discarded. The Shipments sheet does hold five such pairs -- 'Gloves'
    appears as both a Craft worth 170 and a Forge worth 380, and 'Turnip',
    'Squid' and 'Battle Turnip' each have a stray "Category" row -- so
    collapsing the same way is what makes an export agree with the seed that
    was generated. parse_shipment also strips "/" out of Name before keying,
    which is what `strip_slashes` is for.
    """
    out, seen = {}, 0
    for row in csv.DictReader(io.StringIO(csv_text('Rune Factory 4 AP - ' + name))):
        seen += 1
        key = row.get('Name')
        if not key:
            continue
        if strip_slashes:
            key = key.replace('/', '')
        out[key] = row                  # last wins, as upstream
    if seen and not out:
        # Chests, for one, is keyed by APID and has no Name column at all.
        # Say so, rather than handing back an empty table that reads as
        # "the sheet is empty".
        raise SystemExit('the %s sheet has no Name column; read it directly'
                         % name)
    return out if by_name else list(out.values())


def lua_str(s):
    """One Lua string literal, for the tables these tools generate."""
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def slug(name):
    """The pack's code for a name: lowercased, letters and digits only."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


if __name__ == '__main__':
    ap = apworld()
    print('apworld: %s' % source())
    print('  %d locations, %d items'
          % (len(ap.Locations.location_data_table), len(ap.Items.item_data_table)))

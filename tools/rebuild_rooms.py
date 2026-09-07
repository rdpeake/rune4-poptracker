"""Rebuild everything a room change touches, in one go.

Editing a label, an anchor or a `show` flag in `tools/rooms.json` moves the
label on the map, the room's pin, and the name of every barrier and box check
in it. Those live in different files made by different tools, and running them
out of order leaves the pack half-updated -- so run this instead.

    python3 tools/rebuild_rooms.py             do it
    python3 tools/rebuild_rooms.py --dry-run   list the steps and stop

The barrier step needs the apworld in tools/apworld/_input/ and the drawing
steps need the game files in tools/gamedata/_input/. A step whose inputs are
missing is reported and skipped rather than failing the run, so a checkout with
only one of the two still gets as far as it can.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE) + '/'

STEPS = [
    ('room positions, extents and pins', 'gamedata/derive_rooms.py', ['--write']),
    ('where each map is entered',        'gamedata/export_transitions.py', ['--write']),
    ('the map images',                   'gamedata/render_maps.py',  []),
    ('barrier, box and search pins',     'apworld/export_barriers.py', []),
    ('what each area pin covers',        'export_area_refs.py',      ['--write']),
    ('each check its own icon',          'export_section_icons.py',  []),
    ('access rules on every section',    'apply_rules.py',           []),
    ('pins lifted clear of their labels', 'move_pins.py',            ['--write']),
]


def run(script, args):
    return subprocess.run([sys.executable, os.path.join(HERE, script)] + args,
                          capture_output=True, text=True)


def main():
    dry = '--dry-run' in sys.argv
    failed = []
    for i, (what, script, args) in enumerate(STEPS, 1):
        line = '%d/%d  %-36s %s' % (i, len(STEPS), what, script)
        if dry:
            print(line)
            continue
        print(line, flush=True)
        r = run(script, args)
        if r.returncode:
            first = (r.stderr or r.stdout).strip().split('\n')
            print('      SKIPPED -- %s' % (first[0] if first else 'failed'))
            failed.append(what)
        else:
            tail = [l for l in r.stdout.strip().split('\n') if l.strip()]
            for l in tail[-2:]:
                print('      %s' % l.strip()[:96])
    if dry:
        return 0
    if failed:
        print('\n%d step(s) skipped: %s' % (len(failed), ', '.join(failed)))
        print('Check the inputs those need, then run again.')
        return 1
    print('\nRebuilt. Verify with:  python3 tools/verify/check_maps.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())

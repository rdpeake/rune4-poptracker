"""Attach the generated access rules to the pack's location sections.

location_mapping.lua gives AP id -> "@Root/Child/.../Section". Each such section
gets access_rules ["^$RF4Access|<apid>"], which scripts/logic/rf4_rules.lua
evaluates against the clauses exported from the apworld.
"""
import json, glob, re, os, collections

# the pack root, resolved from this script's own location
PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'

# apid -> list of section paths
mapping = collections.defaultdict(list)
src = open(PACK + 'scripts/autotracking/location_mapping.lua', encoding='utf-8').read()
for m in re.finditer(r'\[(\d+)\]\s*=\s*\{([^}]*)\}', src):
    apid = int(m.group(1))
    for pm in re.finditer(r'"([^"]+)"', m.group(2)):
        mapping[apid].append(pm.group(1))

# which apids actually carry clauses
data = open(PACK + 'scripts/logic/rf4_data.lua', encoding='utf-8').read()
loc_block = data.split('RF4_LOC = {')[1]
have_rules = set(int(x) for x in re.findall(r'^\s*\[(\d+)\]', loc_block, re.M))

files = {}
def load(p):
    if p not in files:
        files[p] = json.load(open(p, encoding='utf-8-sig'))
    return files[p]

# index every section by its full path, per file
index = {}
def walk(node, path, path_to_node):
    name = node.get('name')
    here = path + [name] if name else path
    for sec in node.get('sections') or []:
        sname = sec.get('name')
        if sname:
            path_to_node['/'.join(here + [sname])] = sec
    for child in node.get('children') or []:
        walk(child, here, path_to_node)

for p in sorted(glob.glob(PACK + 'locations/*.json')):
    d = load(p)
    p2n = {}
    for root in d:
        walk(root, [], p2n)
    for k, v in p2n.items():
        index.setdefault(k, (p, v))

applied = 0
no_clause = 0
unresolved = []
for apid, paths in mapping.items():
    for raw in paths:
        path = raw.lstrip('@')
        hit = index.get(path)
        if hit is None:
            unresolved.append((apid, raw))
            continue
        if apid not in have_rules:
            # No clauses survived export (its region was dropped as dangling).
            # Still tag it: RF4Access returns Normal for an id with no entry, so
            # the result is the same and the file no longer depends on run order.
            no_clause += 1
        _, node = hit
        # the "^" makes PopTracker read the return as an AccessibilityLevel
        # rather than as an item count; without it a SequenceBreak (5) is just
        # "5 >= 1" and paints green. doc/PACKS.md, "Rules starting with ^".
        # Needs PopTracker >= 0.25.6.
        node['access_rules'] = ["^$RF4Access|%d" % apid]
        # Visibility ANDs the pack's own option toggle (already on the node, if
        # any) with RF4Visible, which answers from the room's actual location
        # list when connected and from the pack's settings when not. No "^"
        # here: visibility rules resolve through the count branch, and
        # RF4Visible returns 0 or 1.
        #
        # The AND has to go INSIDE each element. doc/PACKS.md: the elements of
        # a rules array are OR-ed and commas within one element are AND-ed, so
        # ["opt_dropsanity", "$RF4Visible|1"] reads "dropsanity OR visible",
        # which both ignores RF4Visible while the toggle is on and resurrects
        # the section when it is off. Stripping the term first, rather than the
        # whole element, keeps this idempotent without losing the toggle.
        def without_visible(rule):
            terms = [t for t in rule.split(',')
                     if not t.strip().startswith('$RF4Visible')]
            return ','.join(terms)

        visible = "$RF4Visible|%d" % apid
        vis = [r for r in (without_visible(r) for r in
                           (node.get('visibility_rules') or [])) if r]
        node['visibility_rules'] = [f"{r},{visible}" for r in vis] if vis else [visible]
        applied += 1

for p, d in files.items():
    txt = json.dumps(d, indent=4, ensure_ascii=False)
    # LF: the repo normalised in the .gitattributes commit
    open(p, 'w', encoding='utf-8', newline='\n').write(txt)

print("mapped ap ids        :", len(mapping))
print("sections given rules :", applied)
print("mapped but no clause :", no_clause)
print("unresolved paths     :", len(unresolved), unresolved[:5])
print("files rewritten      :", len(files))

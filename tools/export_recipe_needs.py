"""Name each recipe's grid pin with what the recipe is made of.

A crafted tile badges its ingredients in the strip beneath it, which says what
they are only if you already know the icons -- and a class chip (any Strings,
any Minerals) is the one you are least likely to know by sight. The names are
free: `MapTooltip` prints a `ref` section's OWN name when it has one and falls
back to the target's only when it does not (`maptooltip.cpp:112`), and the line
was pure duplication -- the tooltip's header already reads
`Crafting > Forge > Red Ribbon` and the section under it said `Red Ribbon`
again. So it now reads `Red Ribbon - needs: Red Grass, any Cloths and Skins,
any Strings`, and nothing new is drawn until you point at a tile.

`any X` is not a hedge, it is what the game asks for. Where a slot is a class
the Recipes CSV names one example instead -- `Insect Carapace` for
`Cloths and Skins` -- and in a randomiser that is the difference between a hunt
for one item and a shelf of things that will do.

A repeated slot is a quantity, so four Yarn reads `Yarn x4`. A result the game
gives two recipes reads both: `Recovery Potion - needs: Medicinal Herb, Green
Grass; or: Blue Grass`.

Slots come from `generated/recipes.json` (`gamedata/export_recipes.py`, out of
the game's own tables), so this runs from committed data and needs neither the
apworld nor the game files.

    python3 tools/export_recipe_needs.py
"""
import json
import os
import sys

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
RECIPES = PACK + 'tools/generated/recipes.json'
SRC = 'locations/_Crafting.json'


def spell(slots):
    return ', '.join('%s%s%s' % ('any ' if s['class'] else '', s['name'],
                                 '' if s['count'] == 1 else ' x%d' % s['count'])
                     for s in slots)


def main():
    rec = json.load(open(RECIPES, encoding='utf-8'))['recipes']

    doc = json.load(open(PACK + SRC, encoding='utf-8'))
    root = doc[0] if isinstance(doc, list) else doc
    named, changed, plain = 0, 0, 0
    for node in (root.get('children') or []):
        for sec in (node.get('sections') or []):
            ref = sec.get('ref')
            if not ref:
                continue
            name = ref.rsplit('/', 1)[-1]
            e = rec.get(name)
            if not e:
                # Failed Dish and Disastrous Dish are what a recipe gives you
                # when it goes wrong, so the game has no recipe for them
                plain += 1
                sec.pop('name', None)
                continue
            want = '%s - needs: %s' % (name, '; or: '.join(
                [spell(e['needs'])] + [spell(a) for a in e['alt']]))
            changed += sec.get('name') != want
            sec['name'] = want
            named += 1

    with open(PACK + SRC, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, indent=4, ensure_ascii=False) + '\n')
    print('%d recipe pins named, %d changed, %d left plain'
          % (named, changed, plain))
    return 0


if __name__ == '__main__':
    sys.exit(main())

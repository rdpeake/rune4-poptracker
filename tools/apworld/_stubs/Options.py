"""Just enough of Archipelago's Options for the apworld's own Options.py.

The option classes are read for their `default` and `range_end`, never
instantiated, so a bare class with the attributes the apworld sets is enough.
"""


class _Option:
    default = 0
    range_start = 0
    range_end = 0
    display_name = ''

    def __init__(self, *a, **k):
        pass


class Toggle(_Option): pass
class DefaultOnToggle(_Option): default = 1
class Choice(_Option): pass
class Range(_Option): pass
class OptionList(_Option): default = []
class OptionSet(_Option): default = frozenset()
class FreeText(_Option): default = ''
class Removed(_Option): pass
class DeathLink(_Option): pass
class StartInventoryPool(_Option): pass
class OptionGroup(_Option): pass
class PerGameCommonOptions: pass

"""Just enough of Archipelago's LauncherComponents for the apworld to import."""


class Type:
    CLIENT = 1
    ADJUSTER = 2
    TOOL = 3
    MISC = 4


class Component:
    def __init__(self, *a, **k):
        pass


components = []


def launch_subprocess(*a, **k):
    return None


def launch(*a, **k):
    return None


icon_paths = {}

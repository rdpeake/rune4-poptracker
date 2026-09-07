"""Just enough of Archipelago's settings for the apworld to import.

Only the class shapes are needed: nothing here reads a real setting, and the
paths they hold point at a game install this never touches.
"""


class Group:
    def __init__(self, *a, **k):
        pass


class UserFilePath(str):
    def __new__(cls, *a, **k):
        return str.__new__(cls, '')


class UserFolderPath(UserFilePath): pass
class LocalFolderPath(UserFilePath): pass
class FilePath(UserFilePath): pass


def get_settings():
    return Group()

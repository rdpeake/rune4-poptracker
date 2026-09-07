"""Just enough of Archipelago's Utils for the apworld to import."""
import os


def local_path(*parts):
    return os.path.join(*parts) if parts else ''


def user_path(*parts):
    return local_path(*parts)


def is_windows():
    return os.name == 'nt'


def open_filename(*a, **k):
    return None


class Version(tuple):
    def __new__(cls, *a):
        return tuple.__new__(cls, a)
def visualize_regions(*a, **k):
    return None

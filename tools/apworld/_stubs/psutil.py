"""Just enough of psutil for the apworld's PC client module to import.

Same reason as the pymem stub next door: the apworld's `__init__.py` reaches
`.pc_ap_methods` through `.Save`, and that module finds the running game's
process. Nothing here is called, and an empty process list is the honest
answer for a machine that is reading a location table rather than playing.
"""


def process_iter(*a, **k):
    return iter(())


def pid_exists(pid):
    return False


class NoSuchProcess(Exception):
    pass


class AccessDenied(Exception):
    pass


class Process:
    def __init__(self, *a, **k):
        raise NoSuchProcess('psutil is stubbed in tools/apworld/_stubs')

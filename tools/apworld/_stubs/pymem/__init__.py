"""Just enough of pymem for the apworld's PC client module to import.

`rf4/__init__.py` reaches it through `.Save` -> `.client_methods` ->
`.pc_ap_methods`; see tools/apworld/load.py. Nothing here is ever called, and
`Pymem` raises so a call that does get through fails loudly rather than
returning a plausible zero.
"""


class PymemError(Exception):
    pass


class Pymem:
    process_handle = None

    def __init__(self, *a, **k):
        raise PymemError('pymem is stubbed in tools/apworld/_stubs; '
                         'the pack reads the apworld, it does not run the game')

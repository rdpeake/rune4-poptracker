"""Just enough of Archipelago's NetUtils for the apworld's client to import.

Reached through `.Save` -> `.client_methods` since 2026-09; nothing here is
called. `ClientStatus` carries the real values in case something reads one.
"""
from enum import IntEnum


class NetworkItem:
    def __init__(self, *a, **k):
        pass


class ClientStatus(IntEnum):
    CLIENT_UNKNOWN = 0
    CLIENT_CONNECTED = 5
    CLIENT_READY = 10
    CLIENT_PLAYING = 20
    CLIENT_GOAL = 30


class NetworkPlayer:
    def __init__(self, *a, **k):
        pass


class Hint:
    def __init__(self, *a, **k):
        pass

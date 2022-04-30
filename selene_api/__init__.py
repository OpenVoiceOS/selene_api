from enum import IntEnum


class MicroServiceBackend(IntEnum):
    USER = 0  # user keys on device
    LOCAL = 1  # local backend
    OVOS = 2  # ovos api
    MYCROFT = 3  # selene api
    NEON = 4  # neon api


class MicroServiceAPI:
    def __init__(self, backend=MicroServiceBackend.OVOS):
        self.backend = backend

    def get_weather(self, location):
        """ TODO - use configured backend to do query """

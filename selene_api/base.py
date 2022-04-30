import json
import logging
import os
import requests
from json_database import JsonStorageXDG
from os.path import isfile, expanduser

LOG = logging.getLogger("ovos-selene-api")

OVOS_API = "https://api.openvoiceos.com"
MYCROFT_SELENE = "https://api.mycroft.ai"


class BaseOVOSApi:

    def __init__(self) -> None:
        self.uuid_storage = JsonStorageXDG("ovos_api_uuid")
        self.token_storage = JsonStorageXDG("ovos_api_token")

    def register_device(self):
        if self.check_if_uuid_exists():
            return
        else:
            created_challenge = requests.get(f'{OVOS_API}/create_challenge')
            challenge_response = created_challenge.json()
            register_device_uuid = challenge_response['challenge']
            secret = challenge_response['secret']
            register_device = requests.get(f"{OVOS_API}/register_device/{register_device_uuid}/{secret}")
            self.uuid_storage['uuid'] = register_device_uuid
            self.uuid_storage.store()

    def check_if_uuid_exists(self):
        if "uuid" in self.uuid_storage:
            return True
        return False

    def get_session_challenge(self):
        session_challenge_request = requests.get(f"{OVOS_API}/get_session_challenge")
        session_challenge_response = session_challenge_request.json()
        self.token_storage["challenge"] = session_challenge_response['challenge']
        self.token_storage.store()

    def get_uuid(self):
        return self.uuid_storage.get("uuid", "")

    def get_session_token(self):
        return self.token_storage.get("challenge", "")


class BaseSeleneAPI:
    def __init__(self, url=MYCROFT_SELENE):
        self.url = url

    @property
    def identity(self):
        return load_identity()

    @property
    def uuid(self):
        return self.identity["uuid"]

    @property
    def headers(self):
        return {"Content-Type": "application/json",
                "Device": self.identity['uuid'],
                "Authorization": f"Bearer {self.identity['access']}"}

    def get(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        return requests.get(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def post(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        return requests.post(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def put(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        return requests.put(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

    def patch(self, url=None, *args, **kwargs):
        url = url or self.url
        headers = kwargs.get("headers", {})
        headers.update(self.headers)
        return requests.patch(url, headers=headers, timeout=(3.05, 15), *args, **kwargs)

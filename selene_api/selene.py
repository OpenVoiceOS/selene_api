import json
import logging
import os
import requests
from os.path import isfile, expanduser
from selene_api.base import BaseSeleneAPI, MYCROFT_SELENE, LOG


def load_identity():
    locations = [
        "~/.mycroft/identity/identity2.json",  # old location
        "~/.config/mycroft/identity/identity2.json",  # xdg location
        "~/mycroft-config/identity/identity2.json",  # smartgic docker default loc
    ]
    for loc in locations:
        loc = expanduser(loc)
        if isfile(loc):
            LOG.debug(f"identiTy found: {loc}")
            try:
                with open(loc) as f:
                    return json.load(f)
            except:
                LOG.error("invalid identity file!")
                continue
    return {}


def is_paired(remote=True):
    """ Determine if this device is actively paired with a web backend

       Determines if the installation of  has been paired by the user
       with the backend system, and if that pairing is still active.

       Returns:
           bool: True if paired with backend
       """
    if remote:
        try:
            r = DeviceApi().get()
            if r:
                return True
        except Exception as e:
            pass
        return False
    identity = load_identity()
    if identity["access"] and identity["uuid"]:
        return True
    return False


def has_been_paired():
    """ Determine if this device has ever been paired with a web backend

    Returns:
        bool: True if ever paired with backend (not factory reset)
    """
    return is_paired(remote=False)


class DeviceApi(BaseSeleneAPI):
    def __init__(self, url=f"{MYCROFT_SELENE}/v1/device"):
        super().__init__(url)

    def get(self, url=None, *args, **kwargs):
        """ Retrieve all device information from the web backend """
        url = url or self.url
        return super().get(f"{url}/{self.uuid}").json()

    def get_settings(self):
        """ Retrieve device settings information from the web backend

        Returns:
            str: JSON string with user configuration information.
        """
        return super().get(f"{self.url}/{self.uuid}/setting").json()

    def get_location(self):
        """ Retrieve device location information from the web backend

        Returns:
            str: JSON string with user location.
        """
        return super().get(f"{self.url}/{self.uuid}/location").json()

    def get_subscription(self):
        """
            Get information about type of subscription this unit is connected
            to.

            Returns: dictionary with subscription information
        """
        return super().get(f"{self.url}/{self.uuid}/subscription").json()

    @property
    def is_subscriber(self):
        """
            status of subscription. True if device is connected to a paying
            subscriber.
        """
        try:
            return self.get_subscription().get('@type') != 'free'
        except Exception:
            # If can't retrieve, assume not paired and not a subscriber yet
            return False

    def get_subscriber_voice_url(self, voice=None):
        archs = {'x86_64': 'x86_64', 'armv7l': 'arm', 'aarch64': 'arm'}
        arch = archs.get(os.uname()[4])
        if arch:
            return super().get(f"{self.url}/{self.uuid}/voice?arch={arch}").json().get('link')

    def get_oauth_token(self, dev_cred):
        """
            Get Oauth token for dev_credential dev_cred.

            Argument:
                dev_cred:   development credentials identifier

            Returns:
                json string containing token and additional information
        """
        return super().get(f"{self.url}/{self.uuid}/token/" + str(dev_cred)).json()

    def get_skill_settings(self):
        """Get the remote skill settings for all skills on this device."""
        return super().get(f"{self.url}/{self.uuid}/skill/settings").json()

    def send_email(self, title, body, sender):
        return self.put(f"{self.url}/{self.uuid}/message",
                        json={"title": title,
                              "body": body,
                              "sender": sender}).json()

    def upload_skill_metadata(self, settings_meta):
        """Upload skill metadata.

        Args:
            settings_meta (dict): skill info and settings in JSON format
        """
        return self.put(url=f"{self.url}/{self.uuid}/settingsMeta",
                        json=settings_meta)

    def upload_skills_data(self, data):
        """ Upload skills.json file. This file contains a manifest of installed
        and failed installations for use with the Marketplace.

        Args:
             data: dictionary with skills data from msm
        """
        if not isinstance(data, dict):
            raise ValueError('data must be of type dict')

        _data = dict(data)  # Make sure the input data isn't modified
        # Strip the skills.json down to the bare essentials
        to_send = {}
        if 'blacklist' in _data:
            to_send['blacklist'] = _data['blacklist']
        else:
            LOG.warning('skills manifest lacks blacklist entry')
            to_send['blacklist'] = []

        # Make sure skills doesn't contain duplicates (keep only last)
        if 'skills' in _data:
            skills = {s['name']: s for s in _data['skills']}
            to_send['skills'] = [skills[key] for key in skills]
        else:
            LOG.warning('skills manifest lacks skills entry')
            to_send['skills'] = []

        for s in to_send['skills']:
            # Remove optional fields backend objects to
            if 'update' in s:
                s.pop('update')

            # Finalize skill_gid with uuid if needed
            s['skill_gid'] = s.get('skill_gid', '').replace('@|', f'@{self.uuid}|')
        return self.put(url=self.url + "/" + self.uuid + "/skillJson",
                        json=to_send)


class STTApi(BaseSeleneAPI):
    def __init__(self, url=f"{MYCROFT_SELENE}/v1/stt"):
        super().__init__(url)

    @property
    def headers(self):
        return {"Content-Type": "audio/x-flac",
                "Device": self.identity['uuid'],
                "Authorization": f"Bearer {self.identity['access']}"}

    def stt(self, audio, language="en-us", limit=1):
        """ Web API wrapper for performing Speech to Text (STT)

        Args:
            audio (bytes): The recorded audio, as in a FLAC file
            language (str): A BCP-47 language code, e.g. "en-US"
            limit (int): Maximum minutes to transcribe(?)

        Returns:
            dict: JSON structure with transcription results
        """
        data = self.post(data=audio, params={"lang": language, "limit": limit})
        if data.status_code == 200:
            return data.json()
        raise RuntimeError(f"STT api failed, status_code {data.status_code}")


class GeolocationApi(BaseSeleneAPI):
    """Web API wrapper for performing geolocation lookups."""

    def __init__(self, url=f"{MYCROFT_SELENE}/v1/geolocation"):
        super().__init__(url=url)

    def get_geolocation(self, location):
        """Call the geolocation endpoint.

        Args:
            location (str): the location to lookup (e.g. Kansas City Missouri)

        Returns:
            str: JSON structure with lookup results
        """
        response = self.get(params={"location": location}).json()
        return response['data']


class WolframAlphaApi(BaseSeleneAPI):

    def __init__(self, url=f"{MYCROFT_SELENE}/v1/wolframAlpha"):
        super().__init__(url=url)

    def spoken(self, query, units="metric", lat_lon=None, optional_params=None):
        optional_params = optional_params or {}
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi().get_location()
            lat_lon = (loc['coordinate']['latitude'], loc['coordinate']['longitude'])
        params = {'i': query,
                  'units': units,
                  "geolocation": "{},{}".format(*lat_lon),
                  **optional_params}
        data = self.get(url=f"{self.url}Spoken", params=params)
        return data.text

    def full_results(self, query, units="metric", lat_lon=None, optional_params=None):
        """Wrapper for the WolframAlpha Full Results v2 API.
            https://products.wolframalpha.com/api/documentation/
            Pods of interest
            - Input interpretation - Wolfram's determination of what is being asked about.
            - Name - primary name of
            """
        optional_params = optional_params or {}
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi().get_location()
            lat_lon = (loc['coordinate']['latitude'], loc['coordinate']['longitude'])

        params = {'input': query,
                  "units": units,
                  "geolocation": "{},{}".format(*lat_lon),
                  "mode": "Default",
                  "format": "image,plaintext",
                  "output": "json",
                  **optional_params}
        data = self.get(url=f"{self.url}Full", params=params)
        return data.json()


class OpenWeatherMapApi(BaseSeleneAPI):
    """Use Open Weather Map's One Call API to retrieve weather information"""

    def __init__(self, url=f"{MYCROFT_SELENE}/v1/owm"):
        super().__init__(url)

    @staticmethod
    def owm_language(lang: str):
        """
        OWM supports 31 languages, see https://openweathermap.org/current#multi

        Convert Mycroft's language code to OpenWeatherMap's, if missing use english.

        Args:
            language_config: The Mycroft language code.
        """
        OPEN_WEATHER_MAP_LANGUAGES = (
            "af", "al", "ar", "bg", "ca", "cz", "da", "de", "el", "en", "es", "eu", "fa", "fi", "fr", "gl", "he", "hi",
            "hr", "hu", "id", "it", "ja", "kr", "la", "lt", "mk", "nl", "no", "pl", "pt", "pt_br", "ro", "ru", "se",
            "sk",
            "sl", "sp", "sr", "sv", "th", "tr", "ua", "uk", "vi", "zh_cn", "zh_tw", "zu"
        )
        special_cases = {"cs": "cz", "ko": "kr", "lv": "la"}
        lang_primary, lang_subtag = lang.split('-')
        if lang.replace('-', '_') in OPEN_WEATHER_MAP_LANGUAGES:
            return lang.replace('-', '_')
        if lang_primary in OPEN_WEATHER_MAP_LANGUAGES:
            return lang_primary
        if lang_subtag in OPEN_WEATHER_MAP_LANGUAGES:
            return lang_subtag
        if lang_primary in special_cases:
            return special_cases[lang_primary]
        return "en"

    def get_weather(self, lat_lon=None, lang="en-us", units="metric"):
        """Issue an API call and map the return value into a weather report

        Args:
            units (str): metric or imperial measurement units
            lat_lon (tuple): the geologic (latitude, longitude) of the weather location
        """
        # default to location configured in selene
        if not lat_lon:
            loc = DeviceApi().get_location()
            lat = loc['coordinate']['latitude']
            lon = loc['coordinate']['longitude']
        else:
            lat, lon = lat_lon
        response = self.get(url=f"{self.url}/onecall",
                            params={
                                "lang": self.owm_language(lang),
                                "lat": lat,
                                "lon": lon,
                                "units": units})
        return response.json()


if __name__ == "__main__":
    d = DeviceApi()
    data = d.get_settings()
    print(data)
    # TODO turn these into unittests
    # ident = load_identity()
    # paired = is_paired()
    # geo = GeolocationApi()
    # data = geo.get_geolocation("Lisbon Portugal")
    # print(data)
    # wolf = WolframAlphaApi()
    # data = wolf.spoken("what is the speed of light")
    # print(data)
    # data = wolf.full_results("2+2")
    # print(data)
# owm = OpenWeatherMapApi()
# data = owm.get_weather()
# print(data)

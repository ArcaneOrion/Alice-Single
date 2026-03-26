import json
import logging


logger = logging.getLogger("RequestHeaders")


DEFAULT_REQUEST_HEADER_PROFILES = [
    {
        "User-Agent": "curl/8.0.0",
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "curl/8.4.0",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    },
    {
        "User-Agent": "Wget/1.21.4",
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
]


def _normalize_profiles(profiles):
    normalized = []

    for profile in profiles:
        if not isinstance(profile, dict):
            continue

        clean_profile = {}
        for key, value in profile.items():
            if not isinstance(key, str):
                continue
            if value is None:
                continue

            clean_key = key.strip()
            clean_value = str(value).strip()
            if clean_key and clean_value:
                clean_profile[clean_key] = clean_value

        if clean_profile:
            normalized.append(clean_profile)

    return normalized


def load_request_header_profiles(raw_profiles=None):
    if raw_profiles is None or not str(raw_profiles).strip():
        return [profile.copy() for profile in DEFAULT_REQUEST_HEADER_PROFILES]

    try:
        parsed = json.loads(raw_profiles)
    except json.JSONDecodeError:
        logger.warning("REQUEST_HEADER_PROFILES 不是合法 JSON，回退到默认请求头池。")
        return [profile.copy() for profile in DEFAULT_REQUEST_HEADER_PROFILES]

    normalized = _normalize_profiles(parsed if isinstance(parsed, list) else [])
    if normalized:
        return normalized

    logger.warning("REQUEST_HEADER_PROFILES 为空或格式无效，回退到默认请求头池。")
    return [profile.copy() for profile in DEFAULT_REQUEST_HEADER_PROFILES]


class RequestHeaderRotator:
    def __init__(self, profiles):
        self.profiles = _normalize_profiles(profiles)
        self._index = 0

    def next_profile(self):
        if not self.profiles:
            return 0, {}

        profile_index = self._index % len(self.profiles)
        self._index += 1
        return profile_index + 1, self.profiles[profile_index].copy()

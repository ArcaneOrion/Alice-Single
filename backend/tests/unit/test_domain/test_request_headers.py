"""
请求头策略单元测试

验证 newapi 场景下的默认 curl 风格请求头与轮询策略。
"""

import unittest

from backend.alice.domain.llm.providers.openai_provider import (
    CURL_USER_AGENT,
    DEFAULT_REQUEST_HEADER_PROFILES,
    RequestHeaderRotator,
    ensure_curl_user_agent,
    resolve_request_header_profiles,
)


class TestRequestHeaders(unittest.TestCase):
    """请求头策略测试"""

    def test_any_base_url_uses_default_curl_profiles_when_unconfigured(self) -> None:
        """未显式配置时，所有请求都应启用默认 curl 风格轮询头"""
        profiles = resolve_request_header_profiles(
            "https://openai.api-test.us.ci/v1",
            [],
        )

        self.assertGreaterEqual(len(profiles), 2)
        self.assertTrue(all(profile["User-Agent"] == CURL_USER_AGENT for profile in profiles))
        self.assertTrue(all("Accept" in profile for profile in profiles))

    def test_explicit_profiles_still_force_curl_user_agent(self) -> None:
        """显式配置的 profiles 也必须包含 curl 风格 User-Agent"""
        custom_profiles = [{"User-Agent": "custom-agent", "Accept": "*/*"}]

        profiles = resolve_request_header_profiles(
            "https://api.newapi.ai/v1",
            custom_profiles,
        )

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["User-Agent"], CURL_USER_AGENT)
        self.assertEqual(profiles[0]["Accept"], "*/*")

    def test_ensure_curl_user_agent_overrides_existing_value(self) -> None:
        """最终 extra headers 必须覆盖成 curl 风格 User-Agent"""
        headers = ensure_curl_user_agent(
            {"User-Agent": "OpenAI/Python 2.21.0", "X-Test": "1"}
        )

        self.assertEqual(headers["User-Agent"], CURL_USER_AGENT)
        self.assertEqual(headers["X-Test"], "1")

    def test_request_header_rotator_cycles_profiles(self) -> None:
        """轮换器应按顺序循环返回配置"""
        profiles = [
            {"User-Agent": CURL_USER_AGENT, "Accept": "*/*"},
            {"User-Agent": CURL_USER_AGENT, "Accept": "application/json"},
        ]
        rotator = RequestHeaderRotator(profiles)

        first_index, first_headers = rotator.next_profile()
        second_index, second_headers = rotator.next_profile()
        third_index, third_headers = rotator.next_profile()

        self.assertEqual(first_index, 0)
        self.assertEqual(first_headers, profiles[0])
        self.assertEqual(second_index, 1)
        self.assertEqual(second_headers, profiles[1])
        self.assertEqual(third_index, 0)
        self.assertEqual(third_headers, profiles[0])

    def test_request_header_rotator_handles_no_profiles(self) -> None:
        """空轮换配置应返回空 profile，避免抛错。"""
        rotator = RequestHeaderRotator([])
        index, headers = rotator.next_profile()
        self.assertEqual(index, 0)
        self.assertEqual(headers, {})

    def test_default_profiles_copy_preserves_curl_user_agent(self) -> None:
        """默认轮询表按需拷贝，不会暴露旧表或泄露 UA。"""
        profiles = resolve_request_header_profiles(
            "https://openai.api-test.us.ci/v1",
            None,
        )

        for profile in profiles:
            self.assertEqual(profile["User-Agent"], CURL_USER_AGENT)

        profiles[0]["User-Agent"] = "x"
        self.assertEqual(DEFAULT_REQUEST_HEADER_PROFILES[0]["User-Agent"], CURL_USER_AGENT)


if __name__ == "__main__":
    unittest.main()

import unittest

from request_headers import RequestHeaderRotator, load_request_header_profiles


class RequestHeaderProfilesTest(unittest.TestCase):
    def test_default_profiles_include_curl_8(self):
        profiles = load_request_header_profiles()

        user_agents = [profile.get("User-Agent") for profile in profiles]
        self.assertIn("curl/8.0.0", user_agents)

    def test_rotator_cycles_through_profiles(self):
        rotator = RequestHeaderRotator(
            [
                {"User-Agent": "curl/8.0.0"},
                {"User-Agent": "curl/8.4.0"},
                {"User-Agent": "Wget/1.21.4"},
            ]
        )

        seen = [rotator.next_profile() for _ in range(5)]

        self.assertEqual(
            seen,
            [
                (1, {"User-Agent": "curl/8.0.0"}),
                (2, {"User-Agent": "curl/8.4.0"}),
                (3, {"User-Agent": "Wget/1.21.4"}),
                (1, {"User-Agent": "curl/8.0.0"}),
                (2, {"User-Agent": "curl/8.4.0"}),
            ],
        )

    def test_rotator_returns_copies(self):
        rotator = RequestHeaderRotator([{"User-Agent": "curl/8.0.0"}])

        _, headers = rotator.next_profile()
        headers["User-Agent"] = "mutated"

        _, headers_again = rotator.next_profile()
        self.assertEqual(headers_again["User-Agent"], "curl/8.0.0")


if __name__ == "__main__":
    unittest.main()

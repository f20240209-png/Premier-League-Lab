import contextlib
import io
import unittest
from unittest.mock import Mock, patch

from check_api_football import APIError, APIFootballClient, check, sample_details


class APIFootballCheckTests(unittest.TestCase):
    def test_sampling_keeps_missing_and_zero_distinct_and_limits_calls(self):
        client = Mock()
        client.get.side_effect = [
            {"response": [{"team": {"name": "Example"}, "statistics": [
                {"type": "Total Shots", "value": 0},
                {"type": "Ball Possession", "value": None},
            ]}]},
            {"response": [{"player": {"name": "Player"}, "statistics": [{
                "league": {"id": 39, "season": 2024},
                "games": {"minutes": 90}, "goals": {"total": 0, "assists": None},
            }]}], "paging": {"current": 1, "total": 40}},
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            sample_details(client, 1208021, 2024)
        self.assertIn('"Total Shots": 0', output.getvalue())
        self.assertIn('"assists": null', output.getvalue())
        self.assertEqual(client.get.call_count, 2)
        client.get.assert_any_call("players", league=39, season=2024, page=1)

    def test_failed_statistics_still_samples_players_but_reports_failure(self):
        client = Mock()
        client.get.side_effect = [APIError("Plan denied"), {"response": []}]
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(APIError):
            sample_details(client, 1208021, 2024)
        self.assertEqual(client.get.call_count, 2)

    @patch("check_api_football.requests.get")
    def test_auth_timeout_and_valid_response(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"errors": [], "response": []}
        self.assertEqual(APIFootballClient("test-key").get("leagues", id=39)["response"], [])
        self.assertEqual(get.call_args.kwargs["headers"], {"x-apisports-key": "test-key"})
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 25))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("check_api_football.requests.get")
    def test_http_200_plan_error_is_failure_and_redacts_key(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"errors": {"plan": "test-key cannot access season"}, "response": []}
        with self.assertRaises(APIError) as error:
            APIFootballClient("test-key").get("fixtures", season=2025)
        self.assertNotIn("test-key", str(error.exception))
        self.assertIn("[REDACTED]", str(error.exception))

    @patch("check_api_football.requests.get")
    def test_missing_key_never_requests(self, get):
        with self.assertRaises(APIError):
            APIFootballClient("")
        get.assert_not_called()

    def test_empty_fixtures_are_not_verified(self):
        client = Mock()
        client.get.side_effect = [
            {"response": {"subscription": {}, "requests": {}}},
            {"response": [{"seasons": [{"year": 2025}]}]},
            {"response": []},
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            check(client, 2025)
        self.assertIn("not yet verified", output.getvalue())
        self.assertNotIn("Fixture access verified", output.getvalue())
        self.assertEqual(client.get.call_count, 3)


if __name__ == "__main__":
    unittest.main()

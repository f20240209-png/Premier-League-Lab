"""Read-only API-Football connection/season check; never connects to MySQL."""

import argparse
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URL = "https://v3.football.api-sports.io"
LEAGUE_ID = 39  # English Premier League; API-Football IDs differ from other providers.


class APIError(RuntimeError):
    pass


class APIFootballClient:
    def __init__(self, key, min_interval=6.1):
        if not key or not key.strip() or key.strip() == "paste_your_key_here":
            raise APIError("Set API_FOOTBALL_KEY in the .env beside this script.")
        self.key = key.strip()
        self.min_interval = max(0, min_interval)
        self._last_request = None

    def get(self, endpoint, **params):
        if endpoint not in {"status", "leagues", "fixtures", "fixtures/statistics", "players", "transfers", "players/topscorers", "players/topassists"}:
            raise APIError("Unsupported endpoint.")
        if self._last_request is not None:
            delay = self.min_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
        self._last_request = time.monotonic()
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}",
                headers={"x-apisports-key": self.key},
                params=params,
                timeout=(5, 25),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise APIError("Network request failed. Check your connection and try again.") from None
        if response.status_code != 200:
            raise APIError(f"{endpoint}: HTTP {response.status_code}. Check your key, plan, or quota.")
        try:
            body = response.json()
        except ValueError:
            raise APIError(f"{endpoint}: server returned invalid JSON.") from None
        if not isinstance(body, dict):
            raise APIError(f"{endpoint}: unexpected response format.")
        # This provider can report plan/authentication errors inside an HTTP 200.
        if body.get("errors"):
            detail = json.dumps(body["errors"], ensure_ascii=True).replace(self.key, "[REDACTED]")
            raise APIError(f"{endpoint}: {detail}")
        if "response" not in body:
            raise APIError(f"{endpoint}: response field missing.")
        return body


def check(client, season=None):
    status = client.get("status")["response"]
    subscription = status.get("subscription", {})
    quota = status.get("requests", {})
    print("Connection successful.")
    print(f"Plan: {subscription.get('plan', 'unknown')}; active: {subscription.get('active', 'unknown')}")
    print(f"Daily requests used: {quota.get('current', '?')} / {quota.get('limit_day', '?')}")

    leagues = client.get("leagues", id=LEAGUE_ID)["response"]
    if not leagues:
        raise APIError("No Premier League metadata returned.")
    seasons = leagues[0].get("seasons", [])
    print("Provider-listed seasons:", ", ".join(str(s["year"]) for s in seasons))
    print("Listed seasons describe provider coverage; fixture access must be checked separately.")
    if season is None:
        print("Next: python check_api_football.py --season YEAR (choose a listed start year)")
        return

    selected = next((s for s in seasons if s.get("year") == season), None)
    if not selected:
        raise APIError(f"Season {season} is not listed for the Premier League.")
    print(f"Season: {season}-{season + 1}")
    print("Advertised coverage:", json.dumps(selected.get("coverage", {}), ensure_ascii=True))
    fixtures = client.get("fixtures", league=LEAGUE_ID, season=season)["response"]
    print(f"Fixtures returned: {len(fixtures)}")
    if not fixtures:
        print("No fixtures returned; season data is not yet verified.")
        return
    finished = [m for m in fixtures if m.get("fixture", {}).get("status", {}).get("short") in {"FT", "AET", "PEN"}]
    print(f"Completed fixtures: {len(finished)}")
    sample = finished[0] if finished else fixtures[0]
    print("Sample fixture:", json.dumps({
        "id": sample["fixture"]["id"],
        "date": sample["fixture"].get("date"),
        "home": sample.get("teams", {}).get("home", {}).get("name"),
        "away": sample.get("teams", {}).get("away", {}).get("name"),
        "goals": sample.get("goals"),
    }, ensure_ascii=True))
    print("Fixture access verified. Detailed statistics, player data and transfer fees still need sampling.")


def sample_details(client, fixture_id, season):
    """Two calls only: match statistics and first page of player-season data."""
    failures = []
    try:
        rows = client.get("fixtures/statistics", fixture=fixture_id)["response"]
        print(f"MATCH STATISTICS: fixture {fixture_id}; teams returned: {len(rows)}")
        for row in rows:
            stats = {s.get("type"): s.get("value") for s in row.get("statistics", [])}
            print(json.dumps({
                "team": row.get("team", {}).get("name"),
                **{name: stats.get(name) for name in (
                    "Total Shots", "Shots on Goal", "Ball Possession",
                    "Corner Kicks", "Fouls", "expected_goals",
                )},
            }, ensure_ascii=True))
        if not rows:
            print("No match statistics returned; this sample does not verify coverage.")
    except APIError as error:
        failures.append(str(error))
        print(f"MATCH STATISTICS FAILED: {error}")

    try:
        body = client.get("players", league=LEAGUE_ID, season=season, page=1)
        players = body["response"]
        print(f"PLAYER DATA: {len(players)} players on page 1; pagination: {body.get('paging', {})}")
        for entry in players[:3]:
            player = entry.get("player", {})
            for stats in entry.get("statistics", []):
                league = stats.get("league") or {}
                if league.get("id") != LEAGUE_ID or league.get("season") != season:
                    continue
                games = stats.get("games") or {}
                goals = stats.get("goals") or {}
                print(json.dumps({
                    "player": player.get("name"),
                    "birth_date": (player.get("birth") or {}).get("date"),
                    "team": (stats.get("team") or {}).get("name"),
                    "position": games.get("position"),
                    "minutes": games.get("minutes"),
                    "goals": goals.get("total"),
                    "assists": goals.get("assists"),
                }, ensure_ascii=True))
        if not players:
            print("No player data returned; this sample does not verify coverage.")
    except APIError as error:
        failures.append(str(error))
        print(f"PLAYER DATA FAILED: {error}")
    print("null means missing/unreported, not automatically zero.")
    print("These are small samples, not a season-wide completeness check. Transfer values remain unverified.")
    if failures:
        raise APIError("One or more sample endpoints failed; see messages above.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, help="Season start year, e.g. 2025 for 2025-26")
    parser.add_argument("--sample-fixture", type=int, help="Sample a known fixture's statistics and one player page (2 calls)")
    args = parser.parse_args()
    if args.sample_fixture is not None and (args.sample_fixture <= 0 or args.season is None):
        parser.error("--sample-fixture requires a positive fixture ID and --season")
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    try:
        client = APIFootballClient(os.getenv("API_FOOTBALL_KEY"))
        if args.sample_fixture is not None:
            sample_details(client, args.sample_fixture, args.season)
        else:
            check(client, args.season)
    except APIError as error:
        print(f"CHECK FAILED: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

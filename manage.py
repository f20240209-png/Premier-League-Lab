"""Project commands. Run python manage.py --help."""
import argparse
import getpass
import os
from pathlib import Path
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from check_api_football import APIFootballClient, APIError
from league.storage import open_database
from league.importer import import_season, import_stats, import_players
from league.prediction import train, record_forecasts
from league.demo import seed_demo
from league.bigballs import BigBallsClient, import_bigballs_season
from league.leaderboards import sync_leaders
from league.football_data import FootballDataClient, import_football_data


def main():
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "demo", "hash-password", "sync-real", "sync-players", "compare-models", "sync-squads"):
        sub.add_parser(name)
    for name in ("import-season", "import-stats", "import-players"):
        p = sub.add_parser(name)
        p.add_argument("--season", type=int, required=True)
        if name == "import-season":
            p.add_argument("--provider", choices=["api-football", "bigballs", "football-data"], default="api-football")
        if name != "import-season":
            p.add_argument("--limit", type=int, default=5, help="Maximum requests, 1-40")
    for name in ("train", "forecast"):
        p = sub.add_parser(name)
        p.add_argument("--provider", choices=["api-football", "demo", "real"], default="api-football")
        if name == "train":
            p.add_argument("--test-season", type=int, help="Held-out season start year; required for --provider real")
    p = sub.add_parser("train-values", help="Train the market-value baseline using the bundled real historical dataset")
    p.add_argument("--source-dir", type=Path, help="Folder with players/games/appearances/player_valuations CSV or CSV.GZ files")
    p.add_argument("--first-season", type=int, default=2021)
    p.add_argument("--test-season", type=int, default=2025)
    p.add_argument("--refresh", action="store_true", help="Refresh the four downloaded public files")
    args = parser.parse_args()
    if args.command == "hash-password":
        password = getpass.getpass("New admin password: ")
        if len(password) < 12:
            parser.error("Use at least 12 characters.")
        print("ADMIN_PASSWORD_HASH=" + generate_password_hash(password))
        return 0
    engine, factory = open_database()
    try:
        if args.command == "init":
            print("Analytics tables ready. Existing legacy tables preserved.")
        elif args.command == "train-values":
            from league.value_data import download_source
            from league.value_model import train_value_model, plot_bytes
            from league.storage import ValueModel
            source = args.source_dir
            if args.refresh and source is not None:
                raise ValueError("Use either --refresh or --source-dir, not both.")
            if args.refresh:
                source = download_source(Path(__file__).resolve().parent / 'instance' / 'value-source', refresh=args.refresh)
            mid, report = train_value_model(factory, source, args.first_season, args.test_season)
            print(f"Market-value model {mid}: {report['train_count']} training rows; {report['test_count']} held-out player valuations.")
            print(f"Test MAE: EUR {report['model']['mae_eur']:,.0f}; median baseline: EUR {report['baseline']['mae_eur']:,.0f}.")
            print(f"Test R2: {report['model']['r2']:.3f}. Target: historical market valuation, not transfer fee.")
            destination = Path(__file__).resolve().parent / 'instance' / 'value-reports'
            destination.mkdir(parents=True, exist_ok=True)
            import json
            (destination / f'model-{mid}.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
            with factory() as db:
                (destination / f'model-{mid}.png').write_bytes(plot_bytes(db.get(ValueModel,mid)).getvalue())
            print("Ready: http://127.0.0.1:5000/player-values")
        elif args.command == "demo":
            print(seed_demo(factory))
        elif args.command == "compare-models":
            mid, report = train(factory, "real", test_year=2025, compare=True)
            c = report['comparison']
            print(f"Model {mid}; selected by earlier-season validation: {c['selected']}")
            for name, result in c['candidates'].items():
                print(f"{name}: validation log loss {result['validation']['log_loss']:.3f}; "
                      f"2025/26 accuracy {result['test']['accuracy']:.1%}; log loss {result['test']['log_loss']:.3f}")
            print(f"Benchmark baseline: {report['baseline']['accuracy']:.1%}; log loss {report['baseline']['log_loss']:.3f}")
            print(f"Saved {record_forecasts(factory, 'real')} new pre-kickoff forecasts.")
        elif args.command == "sync-squads":
            from league.squads import sync_squads
            snapshot = sync_squads(factory)
            print(f"Imported {snapshot['player_count']} FPL-listed players across {len(snapshot['clubs'])} clubs for {snapshot['year']}/{snapshot['year']+1}.")
            print("Squad pages now use this snapshot. Historical player statistics and models are unchanged.")
        elif args.command == "sync-players":
            failures = sync_leaders(factory, {
                'api-football': lambda: APIFootballClient(os.getenv('API_FOOTBALL_KEY')),
                'football-data': lambda: FootballDataClient(os.getenv('FOOTBALL_DATA_ORG_KEY')),
                'bigballs': lambda: BigBallsClient(os.getenv('BBS_API_KEY')),
            })
            print("Player sync finished. Check each result above; failed imports preserve previous data.")
            return 1 if failures else 0
        elif args.command == "sync-real":
            # Validate all local keys before spending requests. No keys are printed.
            historical = APIFootballClient(os.getenv("API_FOOTBALL_KEY"))
            previous = FootballDataClient(os.getenv("FOOTBALL_DATA_ORG_KEY"))
            current = BigBallsClient(os.getenv("BBS_API_KEY"))
            print("Importing verified seasons. Each source commits independently; a failure stops the remaining steps.", flush=True)
            print(f"2024/25 API-Football: {import_season(factory, historical, 2024)} matches", flush=True)
            print(f"2025/26 football-data.org: {import_football_data(factory, previous, 2025)} results", flush=True)
            print(f"2026/27 Big Balls Data: {import_bigballs_season(factory, current, 2026)} matches", flush=True)
            mid, report = train(factory, "real", test_year=2025, compare=True)
            print(f"Real model {mid}: {report['train_count']} training, {report['test_count']} held-out matches.")
            print(f"2025/26 test accuracy: {report['model']['accuracy']:.1%}; baseline: {report['baseline']['accuracy']:.1%}.")
            print(f"Saved {record_forecasts(factory, 'real')} new pre-kickoff forecasts.")
            print("Ready: start app.py and open http://127.0.0.1:5000/ without an old season query.")
        elif args.command.startswith("import-"):
            if args.command == "import-season" and args.provider == "football-data":
                count = import_football_data(factory, FootballDataClient(os.getenv("FOOTBALL_DATA_ORG_KEY")), args.season)
                print(f"Imported {count} football-data.org completed results for {args.season}/{args.season + 1}.")
                return 0
            if args.command == "import-season" and args.provider == "bigballs":
                count = import_bigballs_season(factory, BigBallsClient(os.getenv("BBS_API_KEY")), args.season)
                print(f"Imported {count} Big Balls Data fixtures for {args.season}/{args.season + 1}.")
                print("Open http://127.0.0.1:5000/ and select the Big Balls Data season.")
                return 0
            client = APIFootballClient(os.getenv("API_FOOTBALL_KEY"))
            if args.command == "import-season":
                print(f"Imported {import_season(factory, client, args.season)} fixtures. Existing IDs retained.")
            elif args.command == "import-stats":
                print(f"Imported statistics for {import_stats(factory, client, args.season, args.limit)} fixtures.")
            else:
                count, complete = import_players(factory, client, args.season, args.limit)
                print(f"Imported {count} player-team records. Full pagination completed: {complete}.")
        elif args.command == "train":
            mid, report = train(factory, args.provider, test_year=args.test_season)
            print(f"Model {mid}: {report['train_count']} training, {report['test_count']} held-out fixtures.")
            print(f"Held-out accuracy {report['model']['accuracy']:.1%}; baseline {report['baseline']['accuracy']:.1%}.")
            print(f"Log loss {report['model']['log_loss']:.3f}; baseline {report['baseline']['log_loss']:.3f} (lower is better).")
            if args.provider == "demo":
                print("SYNTHETIC DATA: these metrics do not measure real football performance.")
        elif args.command == "forecast":
            print(f"Saved {record_forecasts(factory, args.provider)} new pre-kickoff forecasts.")
        return 0
    except (APIError, ValueError, OSError) as error:
        print(f"FAILED: {error}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

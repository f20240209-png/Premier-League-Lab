"""Compatibility entry point for the non-destructive season importer."""
import os
from dotenv import load_dotenv
from check_api_football import APIFootballClient
from league.importer import import_season
from league.storage import open_database

def sync_all(season):
    load_dotenv()
    engine, factory = open_database()
    try:
        return import_season(factory, APIFootballClient(os.getenv("API_FOOTBALL_KEY")), int(season))
    finally:
        engine.dispose()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    args = parser.parse_args()
    print(f"Imported {sync_all(args.season)} fixtures.")

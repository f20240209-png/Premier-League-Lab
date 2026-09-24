"""Compatibility command: creates missing analytics tables without deleting data."""
from league.storage import open_database
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    engine, _ = open_database()
    engine.dispose()
    print("Analytics tables ready. No existing data was deleted.")

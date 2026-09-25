"""Copy a stopped app's SQLite database to EMPTY PostgreSQL. Dry-run by default."""
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, func, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from league.storage import Base, normalized_url


def migrate(source, target_url, apply=False):
    source = Path(source).resolve(strict=True)
    target_url = normalized_url(target_url)
    if target_url.get_backend_name() != 'postgresql':
        raise ValueError('Target must be PostgreSQL. Your local database is never overwritten.')
    # SQLite opened in read-only mode: a typo cannot create an empty source.
    src = create_engine('sqlite:///file:' + source.as_posix() + '?mode=ro&uri=true')
    dst = create_engine(target_url, pool_pre_ping=True)
    tables = Base.metadata.sorted_tables
    try:
        with src.connect() as reader, reader.begin():
            available = set(inspect(reader).get_table_names())
            if not {t.name for t in tables} <= available:
                raise ValueError('Source is missing V8 tables. Start V8 once before migration.')
            if reader.exec_driver_sql('PRAGMA foreign_key_check').first():
                raise ValueError('Source contains broken foreign keys; migration refused.')
            rows = {t.name: list(reader.execute(select(t)).mappings()) for t in tables}
            if not rows['fl_seasons']:
                raise ValueError('Source has no seasons. Check the database path.')
            with dst.begin() as writer:
                if apply:
                    Base.metadata.create_all(writer)
                    writer.execute(text('LOCK TABLE ' + ', '.join(t.name for t in tables) + ' IN ACCESS EXCLUSIVE MODE'))
                existing = set(inspect(writer).get_table_names())
                for table in tables:
                    if table.name in existing and writer.scalar(select(func.count()).select_from(table)):
                        raise ValueError('Target contains app data. Refusing to merge or overwrite it.')
                if apply:
                    for table in tables:
                        data = rows[table.name]
                        for start in range(0, len(data), 250):
                            writer.execute(table.insert(), data[start:start+250])
                        copied = list(writer.execute(select(table).order_by(table.c.id)).mappings())
                        if copied != sorted(data, key=lambda row: row['id']):
                            raise ValueError('Copy verification failed; transaction rolled back.')
                        writer.execute(text("SELECT setval(pg_get_serial_sequence(:table, 'id'), :next_id, false)"),
                                       {'table': table.name, 'next_id': max((r['id'] for r in data), default=0)+1})
            return {name: len(data) for name, data in rows.items()}
    finally:
        src.dispose()
        dst.dispose()


def main():
    load_dotenv(Path(__file__).with_name('.env'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    target = os.getenv('MIGRATION_TARGET_URL')
    if not target:
        parser.error('Set MIGRATION_TARGET_URL privately; never put credentials in CLI arguments.')
    try:
        counts = migrate(args.source, target, args.apply)
    except (SQLAlchemyError, ValueError, OSError):
        print('Migration refused or failed. Check source schema, empty target, credentials and connectivity. No source data changed.')
        return 1
    print('Migration committed and verified.' if args.apply else 'Dry run passed. No target data changed. Re-run with --apply after backing up.')
    for name, count in counts.items():
        print(f'{name}: {count} rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

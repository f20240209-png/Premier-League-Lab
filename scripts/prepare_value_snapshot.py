"""Rebuild the bundled EPL training extract from the four published source CSVs."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from league.value_data import export_prepared, BUNDLED_DIR

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=BUNDLED_DIR)
    parser.add_argument('--first-season',type=int,default=2021)
    parser.add_argument('--last-season',type=int,default=2025)
    args=parser.parse_args()
    rows,_=export_prepared(args.source_dir,args.destination,args.first_season,args.last_season)
    print(f'Prepared {len(rows)} real player-season examples.')

"""
Script to run the ingestion pipeline: download and parse drug leaflets.

Usage:
    python scripts/run_ingestion.py --drugs CITALOPRAM AZITROMICINA
    python scripts/run_ingestion.py --drugs-file drugs.txt
"""

import argparse
from src.ingestion.download_leaflets import download_leaflets_for_drugs
from src.ingestion.parse_leaflets import parse_leaflets_for_drugs


def parse_args():
    parser = argparse.ArgumentParser(description="Run leaflet ingestion pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--drugs", nargs="+", help="List of drug names to process.")
    group.add_argument(
        "--drugs-file", type=str, help="Path to a file with drug names (one per line)."
    )
    parser.add_argument(
        "--raw-dir", type=str, default="data/raw", help="Directory to save raw PDFs."
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/interim",
        help="Directory to save parsed texts.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.drugs:
        drugs = args.drugs
    else:
        with open(args.drugs_file) as f:
            drugs = [line.strip() for line in f if line.strip()]

    print(f"Downloading leaflets for: {drugs}")
    download_leaflets_for_drugs(drugs, base_dir=args.raw_dir)

    print("Parsing downloaded leaflets...")
    parse_leaflets_for_drugs(
        drugs, raw_dir=args.raw_dir, processed_dir=args.processed_dir
    )

    print("Ingestion pipeline completed.")


if __name__ == "__main__":
    main()

"""
Script to run the ingestion pipeline: download and parse drug leaflets.

Usage:
    python scripts/run_preprocessing.py --drugs-file data/leaflets/estrazione_farmaci.xlsx
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.preprocessing.download_leaflets import (
    download_leaflets_for_drugs,
    parse_drugs_file,
)
from src.preprocessing.map_leaflets import map_drugs_to_leaflet
from src.preprocessing.parse_leaflets import extract_section_from_leaflets


def parse_args():
    parser = argparse.ArgumentParser(description="Run leaflet ingestion pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--drugs-file", type=str, help="Path to a file with drug names (one per line)."
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/leaflets/raw",
        help="Directory to save raw PDFs.",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/leaflets/processed",
        help="Directory to save parsed texts.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse the drugs file to get a list of drugs
    drugs = parse_drugs_file(args.drugs_file)

    # Download leaflets for the drugs
    print(f"Downloading leaflets for: {drugs}")
    # download_leaflets_for_drugs(list(drugs), base_dir=args.raw_dir)

    """
    # Map drugs to leaflets
    map_drugs_to_leaflet(
        args.drugs_file,
        args.raw_dir,
        args.processed_dir,
    )
    """

    # Extract a specific section from the leaflets
    extract_section_from_leaflets(
        args.processed_dir,
        "data/leaflets/sections",
        section_num=2,  # Example section number, adjust as needed
    )


if __name__ == "__main__":
    main()

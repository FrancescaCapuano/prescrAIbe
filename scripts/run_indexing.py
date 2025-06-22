"""
Script to run the retrieval pipeline: load and split drug leaflet PDFs.

Usage:
    python scripts/run_retrieval.py --drugs CITALOPRAM AZITROMICINA
    python scripts/run_retrieval.py --drugs-file drugs.txt
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.indexing.split_documents import split_documents_for_drugs
from src.indexing.vector_db import store_embeddings


def parse_args():
    parser = argparse.ArgumentParser(description="Run leaflet load & split pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--drugs", nargs="+", help="List of drug names to process.")
    group.add_argument(
        "--drugs-file", type=str, help="Path to a file with drug names (one per line)."
    )
    parser.add_argument(
        "--raw-dir", type=str, default="data/raw", help="Directory containing raw PDFs."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.drugs:
        drugs = args.drugs
    else:
        with open(args.drugs_file) as f:
            drugs = [line.strip() for line in f if line.strip()]
    print(f"Loading and splitting PDFs for: {drugs}")
    all_splits = split_documents_for_drugs(drugs, raw_dir=args.raw_dir)
    print("Load and split process completed.")

    print("Storing embeddings for drugs...")
    store_embeddings(all_splits, raw_dir=args.raw_dir)
    print("Embeddings stored in vector database.")


if __name__ == "__main__":
    main()

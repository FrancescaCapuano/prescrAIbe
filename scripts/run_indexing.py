"""
Script to run the retrieval pipeline: load and split drug leaflet PDFs.

Usage:
    python scripts/run_indexing.py --drugs CITALOPRAM AZITROMICINA
    python scripts/run_indexing.py --drugs-file drugs.txt
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.rag.indexing import split_documents_for_drug
from src.rag.indexing import store_embeddings


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

    for drug in drugs:
        print(f"\nProcessing drug: {drug}")
        all_splits = split_documents_for_drug(drug, raw_dir=args.raw_dir)
        print(f"Splitting completed for {drug}.")
        print("Storing embeddings...")
        store_embeddings(all_splits, drug)
        print(f"Embeddings stored in vector database for {drug}.")

    print("All drugs processed.")


if __name__ == "__main__":
    main()

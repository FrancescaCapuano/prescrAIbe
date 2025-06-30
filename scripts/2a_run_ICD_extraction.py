"""
Script to run ICD-11 extraction and/or prepare the vector database base file.

Usage:
    python scripts/2a_run_ICD_extraction.py --extract
    python scripts/2a_run_ICD_extraction.py --prepare-vectordb
    python scripts/2a_run_ICD_extraction.py --extract --prepare-vectordb
"""

import sys
import os
import argparse
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run ICD-11 extraction and/or prepare vectordb base file."
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract ICD-11 codes using icd11_extractor.py",
    )
    parser.add_argument(
        "--prepare-vectordb",
        action="store_true",
        help="Prepare the ICD-11 vector database base file using icd11_prepare_vectordb_base.py",
    )
    # Optional: add arguments for code_filter, chapter_filter, digit_lengths
    parser.add_argument(
        "--code-filter", nargs="*", default=None, help="List of code prefixes to filter"
    )
    parser.add_argument(
        "--chapter-filter",
        nargs="*",
        default=None,
        help="List of chapter names/numbers to filter",
    )
    parser.add_argument(
        "--digit-lengths",
        nargs="*",
        type=int,
        default=None,
        help="List of digit lengths to filter",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output file name for extracted codes",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.extract and not args.prepare_vectordb:
        print("No action specified. Use --extract and/or --prepare-vectordb.")
        return

    if args.extract:
        print("🚀 Running ICD-11 extraction...")
        from src.ICD.icd11_extractor import ICD11Extractor

        # Prepare filters
        code_filter = args.code_filter if args.code_filter else None
        chapter_filter = args.chapter_filter if args.chapter_filter else None
        digit_lengths = args.digit_lengths if args.digit_lengths else None

        extractor = ICD11Extractor(
            code_filter=code_filter,
            chapter_filter=chapter_filter,
            digit_lengths=digit_lengths,
        )
        print("Starting ICD-11 extraction...")

        all_codes = extractor.extract_all_codes()

        output_file = args.output_file or "icd11_extracted_codes.json"
        output_path = extractor.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_codes, f, indent=2, ensure_ascii=False)

        print(f"\nExtraction complete! Found {len(all_codes)} codes.")
        print(f"Data saved to: {output_path}")

    if args.prepare_vectordb:
        print("🚀 Preparing ICD-11 vector database base file...")
        from src.ICD.icd11_prepare_vectordb_base import ICD11VectorDBPreparer

        preparer = ICD11VectorDBPreparer()
        preparer.process()

        # This will run the preparation as per the __main__ block in icd11_prepare_vectordb_base.py


if __name__ == "__main__":
    main()

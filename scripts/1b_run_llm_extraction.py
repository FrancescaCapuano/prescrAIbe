"""
Script to run the LLM extraction pipeline: extract and verify contraindications.

Usage:
    python scripts/run_llm_extraction.py
    python scripts/run_llm_extraction.py --full
    python scripts/run_llm_extraction.py --count 10
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm_extraction.extraction import extract_all_contraindications
from src.llm_extraction.verification import verify_contraindications


def main():
    """Run extraction and verification pipeline."""

    # Check command line arguments
    test_mode = "--full" not in sys.argv
    test_count = 5

    if "--count" in sys.argv:
        try:
            count_index = sys.argv.index("--count") + 1
            test_count = int(sys.argv[count_index])
        except (IndexError, ValueError):
            print("⚠️  Invalid --count argument, using default 5")

    mode_str = f"TEST ({test_count} files)" if test_mode else "FULL"
    print(f"🎯 Running in {mode_str} mode")
    print("💡 Use --full for full processing, --count N to set test count")

    # # Step 1: Extract contraindications
    # print("\n🚀 Step 1: Extracting contraindications...")
    # extract_all_contraindications(
    #     system_prompt_path="data/prompts/system_prompt.txt",
    #     user_prompt_path="data/prompts/user_prompt_template.txt",
    #     leaflet_sections_dir="data/leaflets/sections",
    #     output_file="data/contraindications/all_contraindications.json",
    #     progress_file="data/contraindications/extraction_progress.json",
    #     test_mode=test_mode,
    #     test_count=test_count,
    # )

    # Step 2: Verify contraindications
    print("\n🔍 Step 2: Verifying contraindications...")
    verify_contraindications(
        contraindications_file="data/contraindications/all_contraindications.json",
        leaflet_sections_dir="data/leaflets/sections",
        output_file="data/contraindications/all_contraindications_verified.json",
        unverified_report_file="data/contraindications/unverified_report.json",
    )

    print("\n✅ Pipeline completed!")
    print("📊 Check all_contraindications_verified.json for final results")


if __name__ == "__main__":
    main()

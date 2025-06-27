"""
Script to run the LLM extraction pipeline: extract clinical pathologies.

Usage:
    python scripts/run_llm_extraction.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.llm_extraction.extractor import *

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0


def main():
    """Main function to run the extraction and save results."""
    extract_contraindications(
        leaflet_sections_dir="data/leaflets/sections",
        output_dir="data/contraindications",
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        save_json=True,
    )


if __name__ == "__main__":
    main()

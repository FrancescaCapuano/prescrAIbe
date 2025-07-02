"""
Run this script from the project root to randomly extract 20 ICD codes,
excluding codes that start with M, N, P, Q, R, V, or X.

Usage:
    python src/test/randomizer_select_AICs_test.py
"""

import json
import random

INPUT_FILE = "data/ICD-codes/icd11_vectordb_base.json"
N = 20
EXCLUDE_PREFIXES = {"M", "N", "P", "Q", "R", "V", "X"}


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter out entries where code starts with an excluded prefix
    filtered = [
        entry
        for entry in data
        if "code" in entry
        and entry["code"]
        and entry["code"][0] not in EXCLUDE_PREFIXES
    ]

    # Randomly sample 20 unique entries from the filtered list
    sample = random.sample(filtered, min(N, len(filtered)))

    # Extract only the 'code' key and its value
    codes = [entry["code"] for entry in sample]

    print("Randomly selected ICD codes (excluding M, N, P, Q, R, V, X):")
    for code in codes:
        print(code)


if __name__ == "__main__":
    main()

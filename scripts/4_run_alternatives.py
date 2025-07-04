"""
Script to run the drug alternatives matrix pipeline: merge drug data with ATC codes
and build a matrix of alternative drugs based on ATC classification.

Usage:
    python scripts/4_run_alternatives.py
    python scripts/4_run_alternatives.py --confezioni-path data/drug_alternatives_matrix/confezioni.csv
    python scripts/4_run_alternatives.py --drugs-file data/leaflets/extrazione_farmaci.xlsx --output-dir data/drug_alternatives_matrix --output-file drug_alternatives.json
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import pandas as pd
from collections import defaultdict
import json


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build drug alternatives matrix based on ATC codes"
    )
    parser.add_argument(
        "--confezioni-path",
        type=str,
        default="data/drug_alternatives_matrix/confezioni.csv",
        help="Path to confezioni.csv file with ATC codes",
    )
    parser.add_argument(
        "--drugs-file",
        type=str,
        default="data/leaflets/estrazione_farmaci.xlsx",
        help="Path to estrazione_farmaci.xlsx file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/drug_alternatives_matrix",
        help="Directory to save output files",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="drug_alternatives.json",
        help="Name of output file for alternatives matrix",
    )
    return parser.parse_args()


def merge_estrazione_with_confezioni(confezioni_path, drugs_path):
    """
    Merge estrazione_farmaci with confezioni.csv on codice_aic and code.

    Args:
        confezioni_path: Path to confezioni.csv file
        drugs_path: Path to estrazione_farmaci.xlsx file

    Returns:
        pandas.DataFrame: Merged dataframe with drug and ATC information
    """
    print(f"📂 Loading confezioni data from: {confezioni_path}")
    # read confezioni.csv as df with ; as separator
    confezioni = pd.read_csv(confezioni_path, sep=";")
    confezioni["codice_aic"] = (
        confezioni["codice_aic"].astype(str).str.zfill(9)
    )  # Ensure AIC codes are 9 digits
    print(f"✅ Loaded {len(confezioni)} confezioni records")

    print(f"📂 Loading drugs data from: {drugs_path}")
    # read estrazione farmaci.xlsx as df
    drugs = pd.read_excel(drugs_path)
    drugs["code"] = (
        drugs["code"].astype(str).str.zfill(9)
    )  # Ensure AIC codes are 9 digits
    print(f"✅ Loaded {len(drugs)} drug records")

    # merge the two dataframes on codice_aic and code
    print("🔗 Merging datasets on AIC codes...")
    merged_df = pd.merge(
        drugs,
        confezioni,
        left_on="code",
        right_on="codice_aic",
        how="left",
        suffixes=("", "_confezioni"),
    )

    print(f"✅ Merged dataset contains {len(merged_df)} records")
    return merged_df


def build_drug_alternatives_matrix(merged_df, output_dir, output_file):
    """
    Build a matrix of drug alternatives based on ATC codes.
    Each drug is mapped to its alternatives at different ATC levels.

    Args:
        merged_df: Merged dataframe with drug and ATC information
        output_dir: Directory to save output files
        output_file: Name of output file

    Returns:
        dict: Drug alternatives matrix
    """
    print("🔧 Building drug alternatives matrix...")

    # get rid of rows with empty codice_atc
    initial_count = len(merged_df)
    merged_df = merged_df[
        merged_df["codice_atc"].notna() & (merged_df["codice_atc"].str.strip() != "")
    ]
    print(
        f"📊 Filtered from {initial_count} to {len(merged_df)} records with valid ATC codes"
    )

    drug_alternatives_matrix = defaultdict(list)

    # for each row in merged_df,
    print("⚙️ Processing ATC alternatives...")
    for _, row in merged_df.iterrows():
        codice_aic = row["code"]
        codice_atc = row["codice_atc"].strip()

        current_level = codice_atc
        while len(current_level) > 2:
            # Select all alternatives at the current level
            current_level_alternatives = merged_df[
                merged_df["codice_atc"].str.startswith(current_level)
            ]
            # Get the unique AIC codes for these alternatives
            unique_aic_codes = current_level_alternatives["code"].unique()

            # Add the current AIC code and its alternatives to the matrix if alternative AICs not already present
            drug_alternatives_matrix[codice_aic].extend(
                [
                    aic
                    for aic in unique_aic_codes
                    if aic not in drug_alternatives_matrix[codice_aic]
                ]
            )

            # Move to the next level by removing the last character
            current_level = current_level[:-1]

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Save the drug alternatives matrix to a JSON file
    output_path = Path(output_dir) / output_file
    print(f"💾 Saving alternatives matrix to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(drug_alternatives_matrix, f, indent=2, ensure_ascii=False)

    print(f"✅ Drug alternatives matrix saved successfully!")
    print(f"📊 Total drugs with alternatives: {len(drug_alternatives_matrix)}")

    return drug_alternatives_matrix


def main():
    args = parse_args()

    print(f"\n📊 Configuration:")
    print(f"   Confezioni file: {args.confezioni_path}")
    print(f"   Drugs file: {args.drugs_file}")
    print(f"   Output directory: {args.output_dir}")
    print(f"   Output file: {args.output_file}")

    # Validation
    if not Path(args.confezioni_path).exists():
        print(f"❌ Confezioni file not found: {args.confezioni_path}")
        return

    if not Path(args.drugs_file).exists():
        print(f"❌ Drugs file not found: {args.drugs_file}")
        return

    print(f"\n🚀 Starting drug alternatives matrix pipeline...")

    # Step 1: Load and merge estrazione_farmaci with confezioni.csv to get codice_atc
    merged_df = merge_estrazione_with_confezioni(args.confezioni_path, args.drugs_file)

    # Step 2: Build the drug alternatives matrix
    alternatives_matrix = build_drug_alternatives_matrix(
        merged_df, args.output_dir, args.output_file
    )

    print(f"\n✅ Pipeline completed successfully!")
    print(f"📁 Output saved to: {Path(args.output_dir) / args.output_file}")


if __name__ == "__main__":
    main()

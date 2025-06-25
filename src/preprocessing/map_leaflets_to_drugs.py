import pymupdf4llm
import pathlib
import os
import glob
import re
from typing import List, Tuple
from collections import defaultdict
from download_leaflets import parse_drugs_file
from rapidfuzz import fuzz
from rapidfuzz import process
import pandas as pd
from tqdm import tqdm
import csv


def convert_pdf_to_markdown(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def extract_packages_from_leaflet(leaflet: str) -> List[str]:
    packages = []
    empty_line_seen = False  # Tracks if the first empty line has been seen

    for line in leaflet.split("\n"):
        # Strip leading/trailing whitespace for accurate checks
        line = line.strip()

        # Skip first line if it contains 'foglio illustrativo'
        if "foglio illustrativo" in line.lower():
            continue

        # Handle empty lines
        if not line:
            if not empty_line_seen:
                empty_line_seen = True  # First empty line: skip
                continue
            else:
                break  # Second empty line: exit loop

        # If line starts with ** or contains bold text, store it
        if line.startswith("**") or "**" in line:
            clean_line = line.strip("*").strip()
            if clean_line:
                packages.append(clean_line)
                # print(f"Found package: {clean_line}")

    return packages


def extract_packages_from_start(md_text: str) -> List[str]:
    """
    Extracts packages from the first bold lines before an empty line at the start of the text.
    """
    lines = md_text.split("\n")
    packages = []

    for line in lines:
        line = line.strip()
        if not line:  # Empty line - stop extraction
            break
        # Check if line is bold (between ** and **)
        if line.startswith("**") and line.endswith("**"):
            # Remove bold markers and add to packages
            package = line[2:-2].strip()
            if package:
                packages.append(package)

    return packages


def get_leaflets(md_text: str) -> list:
    """
    Returns a list of (leaflet, packages) tuples.
    """
    pattern = re.compile(r"\*\*[^*]*foglio illustrativo[^*]*\*\*", flags=re.IGNORECASE)
    matches = list(pattern.finditer(md_text))

    if not matches:
        print(f"No 'foglio illustrativo' matches found")
        packages = extract_packages_from_start(md_text)
        return [(md_text.strip(), packages)]

    filtered_matches = [
        m
        for m in matches
        if "questo foglio illustrativo è stato aggiornato" not in m.group(0).lower()
    ]

    if not filtered_matches:
        print(f"All matches filtered out")
        packages = extract_packages_from_start(md_text)
        return [(md_text.strip(), packages)]

    leaflets = []
    for i, match in enumerate(filtered_matches):
        start = match.start()
        end = filtered_matches[i + 1].start() if i + 1 < len(filtered_matches) else None
        leaflet = md_text[start:end].strip()
        packages = extract_packages_from_leaflet(leaflet)
        if packages:
            leaflets.append((leaflet, packages))
    return leaflets


def normalize(text):
    normalization_map = {
        "RIV": "rivestite",
        "EFF": "effervescenti",
        "CPR": "compresse",
        "INF": "infusione",
    }
    text = text.upper()
    for k, v in normalization_map.items():
        text = re.sub(r"\b{}\b".format(k), v, text)
    return text


def score_mapping(drug_name: str, package: str) -> float:
    # print(normalize(drug_name))
    return fuzz.token_sort_ratio(normalize(drug_name), package)


def best_mapping(drug_name, mappings: List[Tuple[str, float]]) -> Tuple[str, float]:
    """
    Returns the best mapping from a list of (package, score) tuples.
    """
    match, score, _ = process.extractOne(
        normalize(drug_name),
        [package for (package, index) in mappings],
        scorer=fuzz.token_sort_ratio,
    )
    # print(f"\n📦 Package: {drug_name}\n📄 Best Match: {match}\n🔢 Score: {score:.2f}")
    return (match, score)


def save_matched_leaflet(matched_leaflet, processed_dir, aic, fi_file):
    filename = fi_file.split("/")[-1]
    new_filename = filename.split(".")[0] + str(aic)[-2:] + ".md"
    output_path = processed_dir + "/" + new_filename
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(matched_leaflet)


def map_drug_to_leaflet(
    drug_name: str, aic6: str, aic: str, raw_dir: str, processed_dir: str
):
    """
    Maps a drug name to its corresponding leaflet file name.
    Assumes the drugs_file is a CSV with a 'drug_name' column.
    """
    fi_files = glob.glob(f"data/leaflets/raw/FI_*_{aic6}.pdf")

    for fi_file in fi_files:

        md_text = convert_pdf_to_markdown(fi_file)

        leaflets = get_leaflets(md_text)
        if len(leaflets) == 1 and isinstance(leaflets[0], str):
            print(f"⚠️  No valid 'foglio illustrativo' header found in: {fi_file}")
            continue  # Skip to the next file

        if leaflets:
            mappings = []
            for index, (leaflet, packages) in enumerate(leaflets):
                # print(f"\nProcessing leaflet {index + 1}")
                mappings_leaflet = [(package, index) for package in packages]
                # print(mappings_leaflet)
                mappings += mappings_leaflet

            match, score = best_mapping(drug_name, mappings)

            # Find leaflet index based on the matched package
            leaflet_index = next(
                (index for package, index in mappings if package == match), None
            )

            matched_leaflet = leaflets[leaflet_index][0]

            save_matched_leaflet(matched_leaflet, processed_dir, aic, fi_file)


def map_drugs_to_leaflet(drugs_file: str, raw_dir: str, processed_dir: str) -> None:
    """
    Maps each drug in the drugs_file to its corresponding leaflet file.
    Saves each mapping to CSV as soon as it is found.
    """
    drugs = list(parse_drugs_file(drugs_file, split_name=False, aic=True))
    csv_path = "drug_leaflet_mapping.csv"
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["drug_name", "mapping"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for drug_name, aic, aic6 in tqdm(drugs, desc="Mapping drugs to leaflets"):
            best_mapping = map_drug_to_leaflet(
                drug_name, aic6, aic, raw_dir, processed_dir
            )
            if best_mapping:
                writer.writerow(
                    {
                        "drug_name": drug_name,
                        "mapping": best_mapping,
                    }
                )
                csvfile.flush()  # Ensure it's written immediately
            print("-" * 80)


if __name__ == "__main__":

    import pdb

    # Path to your Excel file
    drugs_file = "/home/francesca/Desktop/DS Bootcamp/portfolio_project/rxassist-ai/data/leaflets/estrazione_farmaci.xlsx"

    # Identify and save corresponding leaflet for each drug
    map_drugs_to_leaflet(drugs_file, "data/leaflets/raw", "data/leaflets/processed")

    pdb.set_trace()

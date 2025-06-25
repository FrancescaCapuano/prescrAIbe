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
    Returns None if no valid mappings are found.
    """
    if not mappings:
        print(f"No mappings available for {drug_name}")
        return None

    packages = [package for (package, index) in mappings if package and package.strip()]
    if not packages:
        print(f"No valid packages found for {drug_name}")
        return None

    result = process.extractOne(
        normalize(drug_name),
        packages,
        scorer=fuzz.token_sort_ratio,
    )

    if result is None:
        print(f"No match found for {drug_name}")
        return None

    match, score, _ = result
    # print(f"\n📦 Package: {drug_name}\n📄 Best Match: {match}\n🔢 Score: {score:.2f}")
    return (match, score)


def save_matched_leaflet(matched_leaflet, processed_dir, aic, fi_file):
    filename = fi_file.split("/")[-1]
    new_filename = filename.split(".")[0] + str(aic)[-3:] + ".md"
    output_path = processed_dir + "/" + new_filename

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(matched_leaflet)


def get_leaflets(md_text: str) -> list:
    """
    Returns a list of (leaflet, packages) tuples.
    """
    # Updated pattern: only matches single-line bold headers containing "foglio illustrativo"
    pattern = re.compile(
        r"^\*\*[^*\n]*foglio illustrativo[^*\n]*\*\*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    matches = list(pattern.finditer(md_text))

    if not matches:
        print(f"No 'foglio illustrativo' matches found")
        return [(md_text.strip(), ["package"])]

    filtered_matches = [
        m
        for m in matches
        if "foglio illustrativo è stato" not in m.group(0).lower()
        and "revisione del foglio illustrativo" not in m.group(0).lower()
        and "contenuto di questo foglio illustrativo" not in m.group(0).lower()
        and "deve leggere il foglio illustrativo" not in m.group(0).lower()
        and "attentamente questo foglio illustrativo" not in m.group(0).lower()
        and "revisione del foglio illustrativo" not in m.group(0).lower()
    ]

    if not filtered_matches:
        print(f"All matches filtered out")
        return [(md_text.strip(), ["package"])]

    leaflets = []
    for i, match in enumerate(filtered_matches):
        start = match.start()
        end = filtered_matches[i + 1].start() if i + 1 < len(filtered_matches) else None
        leaflet = md_text[start:end].strip()
        packages = extract_packages_from_leaflet(leaflet)
        if packages:
            leaflets.append((leaflet, packages))
    return leaflets


def map_drug_to_leaflet(
    drug_name: str, aic6: str, aic: str, raw_dir: str, processed_dir: str
):
    """
    Maps a drug name to its corresponding leaflet file name.
    Returns (drug_name, match) if more than one leaflet is found, None otherwise.
    Skips processing if leaflet already exists.
    """
    fi_files = glob.glob(f"data/leaflets/raw/FI_*_{aic6}.pdf")

    for fi_file in fi_files:
        # Check if leaflet already exists
        filename = fi_file.split("/")[-1]
        new_filename = filename.split(".")[0] + str(aic)[-3:] + ".md"
        output_path = os.path.join(processed_dir, new_filename)

        if os.path.exists(output_path):
            # print(f"⏭️  Leaflet already exists for {drug_name}: {output_path}")
            continue  # Skip to next file
        md_text = convert_pdf_to_markdown(fi_file)

        leaflets = get_leaflets(md_text)
        if len(leaflets) == 1 and isinstance(leaflets[0], str):
            print(f"⚠️  No valid 'foglio illustrativo' header found in: {fi_file}")
            continue  # Skip to the next file

        if leaflets:
            mappings = []
            for index, (leaflet, packages) in enumerate(leaflets):
                mappings_leaflet = [(package, index) for package in packages]
                mappings += mappings_leaflet

            mapping_result = best_mapping(drug_name, mappings)
            if mapping_result is None:
                print(f"❌ No valid mapping found for {drug_name}")
                continue

            match, score = mapping_result

            # Find leaflet index based on the matched package
            leaflet_index = next(
                (index for package, index in mappings if package == match), None
            )

            matched_leaflet = leaflets[leaflet_index][0]

            save_matched_leaflet(matched_leaflet, processed_dir, aic, fi_file)

            # Return (drug_name, match) only if more than one leaflet was found
            if len(leaflets) > 1:
                return (drug_name, match)

    return None


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
            mapping = map_drug_to_leaflet(drug_name, aic6, aic, raw_dir, processed_dir)
            if mapping:
                writer.writerow(
                    {
                        "drug_name": mapping[0],
                        "mapping": mapping[1],
                    }
                )
                csvfile.flush()  # Ensure it's written immediately
            print("-" * 80)


def debug_mapping_for_file(
    filename: str, processed_dir: str, raw_dir: str = "data/leaflets/raw"
):
    """
    Debugging function to trace the mapping process for a specific file.
    Compares drug name with all packages in the corresponding leaflets.
    """
    # Ensure filename is valid
    if not filename or not isinstance(filename, str):
        print(f"Invalid filename: {filename}")
        return

    # Step 1: Look for foglio illustrativo patterns - USE THE SAME PATTERN AS get_leaflets
    pattern = re.compile(
        r"^\*\*[^*\n]*foglio illustrativo[^*\n]*\*\*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    matches = list(pattern.finditer(md_text))
    print(f"   Step 1: Found {len(matches)} 'foglio illustrativo' matches")

    for i, match in enumerate(matches):
        print(
            f"      Match {i}: '{match.group(0)}' at position {match.start()}-{match.end()}"
        )

    # ... rest of the code remains the same ...
    fi_files = glob.glob(f"data/leaflets/raw/FI_*_{filename}.pdf")

    for fi_file in fi_files:
        md_text = convert_pdf_to_markdown(fi_file)

        leaflets = get_leaflets(md_text)
        if len(leaflets) == 1 and isinstance(leaflets[0], str):
            print(f"⚠️  No valid 'foglio illustrativo' header found in: {fi_file}")
            continue  # Skip to the next file

        if leaflets:
            for index, (leaflet, packages) in enumerate(leaflets):
                print(f"   Leaflet {index + 1}: {len(packages)} packages found")
                for package in packages:
                    score = score_mapping(filename, package)
                    print(f"      Package: {package} - Score: {score}")
        else:
            print(f"❌ No valid leaflets found in {fi_file}")


if __name__ == "__main__":
    map_drugs_to_leaflet(
        "data/leaflets/estrazione_farmaci.xlsx",
        "data/leaflets/raw",
        "data/leaflets/processed",
    )

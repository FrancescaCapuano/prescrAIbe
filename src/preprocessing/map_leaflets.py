import pymupdf4llm
import pathlib
import os
import glob
import re
from typing import List, Tuple
from collections import defaultdict
from rapidfuzz import fuzz
from rapidfuzz import process
import pandas as pd
from tqdm import tqdm
import csv
import json

try:
    from .download_leaflets import parse_drugs_file
except ImportError:
    # If running as script, use absolute import
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from preprocessing.download_leaflets import parse_drugs_file


def convert_pdf_to_markdown(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def extract_packages_from_leaflet(leaflet: str) -> List[str]:
    packages = []
    lines = leaflet.split("\n")

    # Skip the first line if it contains 'foglio illustrativo'
    start_idx = 0
    if lines and "foglio illustrativo" in lines[0].lower():
        start_idx = 1

    # Look at the first 20 lines after the header for packages
    for i in range(start_idx, min(len(lines), start_idx + 20)):
        line = lines[i].strip()

        if not line:
            continue

        # Look for bold text OR lines that look like drug names
        if (
            line.startswith("**")
            or "**" in line
            or
            # Also look for lines with drug-like patterns
            any(
                keyword in line.upper()
                for keyword in ["MG", "ML", "CPR", "FL", "MCGS", "UI"]
            )
        ):

            clean_line = line.strip("*").strip()
            if clean_line and len(clean_line) > 3:  # Avoid very short strings
                packages.append(clean_line)

    # If still no packages found, use a fallback
    if not packages:
        # Extract any non-empty line from the first 10 lines
        for i in range(start_idx, min(len(lines), start_idx + 10)):
            line = lines[i].strip()
            if line and len(line) > 5:
                packages.append(line.strip("*").strip())
                break

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


def best_mapping(
    drug_name, mappings: List[Tuple[str, float]]
) -> Tuple[str, float] | None:
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
    # More specific pattern: only matches bold headers that START with "foglio illustrativo"
    # and are likely to be actual leaflet headers
    pattern = re.compile(
        r"^\*\*\s*foglio illustrativo[^*\n]*\*\*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    matches = list(pattern.finditer(md_text))

    if not matches:
        print(f"No 'foglio illustrativo' matches found")
        return [(md_text.strip(), ["package"])]

    # Filter out metadata patterns, but keep valid leaflet headers
    filtered_matches = []
    for m in matches:
        match_text = m.group(0).lower()

        # Only filter out clear metadata patterns
        is_metadata = any(
            phrase in match_text
            for phrase in [
                "foglio illustrativo è stato",
                "revisione del foglio illustrativo",
                "aggiornamento del foglio illustrativo",
            ]
        )

        # Keep if it's not metadata
        if not is_metadata:
            filtered_matches.append(m)

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


def map_drugs_to_leaflet(drugs_file: str, raw_dir: str, processed_dir: str) -> None:
    """
    Maps each drug to its leaflet and tracks ALL outcomes.
    Saves comprehensive mapping data including ICD codes to CSV.
    """
    drugs = list(parse_drugs_file(drugs_file, split_name=False, aic=True))

    # CSV setup
    csv_path = "data/leaflets/drugs_leaflet_mapping.csv"
    fieldnames = [
        "drug_name",
        "aic_full",
        "aic6",
        "status",
        "leaflet_file",
        "matched_package",
        "match_score",
        "total_leaflets_found",
        "pdf_file",
        "icd_codes",  # Add ICD codes column
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for drug_name, aic, aic6 in tqdm(drugs, desc="Comprehensive mapping"):
            row_data = {
                "drug_name": drug_name,
                "aic_full": aic,
                "aic6": aic6,
                "status": "unknown",
                "leaflet_file": "",
                "matched_package": "",
                "match_score": 0,
                "total_leaflets_found": 0,
                "pdf_file": "",
                "icd_codes": "",
            }

            # Step 1: Check for PDF files
            fi_files = glob.glob(f"data/leaflets/raw/FI_*_{aic6}.pdf")
            if not fi_files:
                row_data["status"] = "no_pdf_found"
                writer.writerow(row_data)
                continue

            row_data["pdf_file"] = fi_files[0]

            # Step 2: Check if leaflet already exists
            filename = fi_files[0].split("/")[-1]
            new_filename = filename.split(".")[0] + str(aic)[-3:] + ".md"
            output_path = os.path.join(processed_dir, new_filename)

            if os.path.exists(output_path):
                row_data["status"] = "already_processed"
                row_data["leaflet_file"] = new_filename
                # Try to get ICD codes if available
                row_data["icd_codes"] = get_icd_codes_for_aic(aic)
                writer.writerow(row_data)
                continue

            try:
                # Step 3: Convert PDF to markdown
                md_text = convert_pdf_to_markdown(fi_files[0])
                leaflets = get_leaflets(md_text)

                if not leaflets:
                    row_data["status"] = "no_leaflets_extracted"
                    row_data["icd_codes"] = get_icd_codes_for_aic(aic)
                    writer.writerow(row_data)
                    continue

                row_data["total_leaflets_found"] = len(leaflets)

                # Step 4: Find best mapping
                mappings = []
                for index, (leaflet, packages) in enumerate(leaflets):
                    mappings_leaflet = [(package, index) for package in packages]
                    mappings += mappings_leaflet

                mapping_result = best_mapping(drug_name, mappings)
                if mapping_result is None:
                    row_data["status"] = "no_valid_mapping"
                    row_data["icd_codes"] = get_icd_codes_for_aic(aic)
                    writer.writerow(row_data)
                    continue

                match, score = mapping_result
                row_data["matched_package"] = match
                row_data["match_score"] = score

                # Step 5: Find leaflet index and save
                leaflet_index = next(
                    (index for package, index in mappings if package == match), None
                )

                if leaflet_index is None:
                    row_data["status"] = "leaflet_index_not_found"
                    row_data["icd_codes"] = get_icd_codes_for_aic(aic)
                    writer.writerow(row_data)
                    continue

                # Step 6: Save the matched leaflet
                matched_leaflet = leaflets[leaflet_index][0]
                save_matched_leaflet(matched_leaflet, processed_dir, aic, fi_files[0])

                row_data["status"] = "successfully_mapped"
                row_data["leaflet_file"] = new_filename
                row_data["icd_codes"] = get_icd_codes_for_aic(aic)

                writer.writerow(row_data)

            except Exception as e:
                row_data["status"] = f"error: {str(e)}"
                row_data["icd_codes"] = get_icd_codes_for_aic(aic)
                writer.writerow(row_data)
                print(f"❌ Error processing {drug_name} (AIC: {aic}): {e}")
                continue

        csvfile.flush()

    print(f"\n✅ Comprehensive mapping saved to: {csv_path}")
    print_mapping_summary(csv_path)


def get_icd_codes_for_aic(aic: str) -> str:
    """
    Get ICD codes associated with an AIC from contraindications data.
    Returns comma-separated string of ICD codes.
    """
    try:
        # Load contraindications data
        contraindications_file = (
            "../../data/contraindications/all_contraindications_verified.json"
        )
        if not os.path.exists(contraindications_file):
            return ""

        with open(contraindications_file, "r", encoding="utf-8") as f:
            contraindications_data = json.load(f)

        # Find AIC in contraindications
        aic_data = contraindications_data.get(aic, {})
        if not aic_data:
            return ""

        # Extract ICD codes from contraindications
        icd_codes = set()
        for contraindication in aic_data.get("contraindications", []):
            # Look for ICD codes in the contraindication text
            # This is a simple pattern - you might need to adjust based on your data structure
            text = contraindication.get("contraindication", "")
            # Simple regex to find ICD-11 codes (pattern: letters/numbers)
            icd_matches = re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", text)
            icd_codes.update(icd_matches)

        return ",".join(sorted(icd_codes)) if icd_codes else ""

    except Exception as e:
        print(f"Warning: Could not get ICD codes for AIC {aic}: {e}")
        return ""


def print_mapping_summary(csv_path: str) -> None:
    """Print summary statistics from the mapping CSV."""
    try:
        df = pd.read_csv(csv_path)

        print("\n📊 MAPPING SUMMARY:")
        print("-" * 50)

        # Status distribution
        status_counts = df["status"].value_counts()
        print("Status Distribution:")
        for status, count in status_counts.items():
            percentage = (count / len(df)) * 100
            print(f"  {status}: {count} ({percentage:.1f}%)")

        # Success rate
        success_count = len(df[df["status"] == "successfully_mapped"])
        already_processed = len(df[df["status"] == "already_processed"])
        total_processed = success_count + already_processed

        print(f"\nOverall Results:")
        print(f"  Total AICs: {len(df)}")
        print(f"  Successfully mapped: {success_count}")
        print(f"  Already processed: {already_processed}")
        print(f"  Total with leaflets: {total_processed}")
        print(f"  Success rate: {(total_processed/len(df)*100):.1f}%")

        # ICD codes statistics
        with_icd = len(df[df["icd_codes"] != ""])
        print(f"  AICs with ICD codes: {with_icd} ({(with_icd/len(df)*100):.1f}%)")

    except Exception as e:
        print(f"Error reading summary: {e}")


def debug_pdf_availability(drugs_file: str) -> None:
    """
    Debug function to check how many drugs have corresponding PDF files.
    """
    print("🔍 Debugging PDF availability...")

    # Load drugs data
    try:
        drugs = list(parse_drugs_file(drugs_file, split_name=False, aic=True))
        print(f"✅ Loaded {len(drugs)} drugs from file")
    except Exception as e:
        print(f"❌ Error loading drugs: {e}")
        return

    # Statistics
    stats = {
        "total_drugs": len(drugs),
        "pdfs_found": 0,
        "pdfs_not_found": 0,
        "multiple_pdfs": 0,
    }

    # Lists to track details
    drugs_with_pdfs = []
    drugs_without_pdfs = []
    drugs_with_multiple_pdfs = []

    print("\n🔍 Checking PDF availability for each drug...")

    for i, (drug_name, aic, aic6) in enumerate(drugs):
        # Look for PDF files
        pdf_pattern = f"../../data/leaflets/raw/FI_*_{aic6}.pdf"
        fi_files = glob.glob(pdf_pattern)

        if len(fi_files) == 0:
            stats["pdfs_not_found"] += 1
            drugs_without_pdfs.append((drug_name, aic, aic6))
        elif len(fi_files) == 1:
            stats["pdfs_found"] += 1
            drugs_with_pdfs.append((drug_name, aic, aic6, fi_files[0]))
        else:
            stats["pdfs_found"] += 1
            stats["multiple_pdfs"] += 1
            drugs_with_multiple_pdfs.append((drug_name, aic, aic6, fi_files))

        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(drugs)} drugs...")

    # Print summary
    print("\n📊 PDF AVAILABILITY SUMMARY:")
    print("-" * 50)
    print(f"Total drugs: {stats['total_drugs']}")
    print(
        f"PDFs found: {stats['pdfs_found']} ({stats['pdfs_found']/stats['total_drugs']*100:.1f}%)"
    )
    print(
        f"PDFs not found: {stats['pdfs_not_found']} ({stats['pdfs_not_found']/stats['total_drugs']*100:.1f}%)"
    )
    print(f"Multiple PDFs: {stats['multiple_pdfs']}")

    # Show some examples
    if drugs_with_pdfs:
        print(f"\n✅ First 5 drugs WITH PDFs:")
        for i, (drug_name, aic, aic6, pdf_file) in enumerate(drugs_with_pdfs[:5]):
            print(f"  {i+1}. {drug_name} (AIC: {aic6}) -> {pdf_file}")

    if drugs_without_pdfs:
        print(f"\n❌ First 5 drugs WITHOUT PDFs:")
        for i, (drug_name, aic, aic6) in enumerate(drugs_without_pdfs[:5]):
            print(
                f"  {i+1}. {drug_name} (AIC: {aic6}) -> Pattern: data/leaflets/raw/FI_*_{aic6}.pdf"
            )

    if drugs_with_multiple_pdfs:
        print(f"\n📄 Drugs with MULTIPLE PDFs:")
        for drug_name, aic, aic6, pdf_files in drugs_with_multiple_pdfs:
            print(f"  {drug_name} (AIC: {aic6}) -> {len(pdf_files)} files: {pdf_files}")

    # Check if raw directory exists
    raw_dir = "../../data/leaflets/raw"
    if not os.path.exists(raw_dir):
        print(f"\n❌ WARNING: Raw directory doesn't exist: {raw_dir}")
    else:
        # Count total PDF files in directory
        all_pdfs = glob.glob(f"{raw_dir}/*.pdf")
        fi_pdfs = glob.glob(f"{raw_dir}/FI_*.pdf")
        print(f"\n📁 Directory info:")
        print(f"  Raw directory: {raw_dir}")
        print(f"  Total PDF files: {len(all_pdfs)}")
        print(f"  FI_*.pdf files: {len(fi_pdfs)}")

        # Show sample of actual PDF files
        print(f"\n📄 Sample of actual PDF files found:")
        for i, pdf_file in enumerate(fi_pdfs[:5]):
            filename = os.path.basename(pdf_file)
            print(f"  {i+1}. {filename}")

    return stats


# Test function
if __name__ == "__main__":
    drugs_file = "../../data/leaflets/estrazione_farmaci.xlsx"
    debug_pdf_availability(drugs_file)

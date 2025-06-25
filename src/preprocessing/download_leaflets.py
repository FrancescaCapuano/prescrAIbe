import requests
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd
import csv
from tqdm import tqdm


def get_drug_data(drug_name: str, page: int = 0) -> Dict[str, Any]:
    """
    Query the AIFA API for drug data.

    Args:
        drug_name (str): Name of the drug to search.
        page (int): Page number for pagination.

    Returns:
        dict: JSON response from the API.
    """
    url = "https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/formadosaggio/ricerca"
    params = {"query": drug_name, "spellingCorrection": "true", "page": page}
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def download_pdf(url: str, filename: str) -> None:
    """
    Download a PDF from a URL and save it to a file.

    Args:
        url (str): The URL to download the PDF from.
        filename (str): The path to save the PDF file.
    """
    response = requests.get(url)
    response.raise_for_status()

    Path(os.path.dirname(filename)).mkdir(parents=True, exist_ok=True)
    with open(filename, "wb") as f:
        f.write(response.content)


def save_leaflets(
    drug_name: str, aic6_code: str, base_dir: str = "data/leaflets/raw"
) -> Optional[str]:
    """
    Download all available leaflets (FI and RCP) for a given drug and aic_code.
    Returns a failure reason string if no match or download fails, else None.
    Skips download if file already exists.
    """
    matches = 0
    page = 0
    download_failed = False
    while True:
        data = get_drug_data(drug_name, page=page)
        content = data.get("data", {}).get("content", [])
        if not content:
            if page == 0:
                return "no result"
            break

        for result in content:
            codice_sis = result["medicinale"]["codiceSis"]
            aic6 = result["medicinale"]["aic6"]

            if str(aic6) == str(aic6_code).lstrip("0"):
                matches += 1
                urls = {
                    "FI": f"https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/{codice_sis}/farmaci/{aic6}/stampati?ts=FI",
                    "RCP": f"https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/{codice_sis}/farmaci/{aic6}/stampati?ts=RCP",
                }
                for kind, url in urls.items():
                    filename = os.path.join(
                        base_dir,
                        f"{kind}_{str(codice_sis).zfill(6)}_{str(aic6).zfill(6)}.pdf",
                    )
                    if os.path.exists(filename):
                        print(f"Already exists, skipping: {filename}")
                        continue
                    try:
                        download_pdf(url, filename)
                        print(f"Downloaded: {filename}")
                    except requests.HTTPError as e:
                        print(f"Failed to download {kind} for {aic6}: {e}")
                        download_failed = True
                break
        page += 1
    if matches == 0:
        return "no result"
    if download_failed:
        return "download problem"
    return None


def split_name_and_dosage(row):
    parts = str(row["name"]).split("*")
    if len(parts) == 2:
        return pd.Series({"name": parts[0].strip(), "dosaggio": parts[1].strip()})
    else:
        return pd.Series({"name": row["name"], "dosaggio": row["name"]})


def parse_drugs_file(
    drugs_file: str, split_name: bool = True, aic: bool = False
) -> set:
    """
    Reads an Excel file containing drug names and codes and returns a set of (drug_name, aic6) tuples.
    aic6 is the first 6 digits of the 'code' column.
    Assumes columns are named 'name' and 'code'.
    """
    df = pd.read_excel(drugs_file)

    if split_name:
        df[["name", "dosaggio"]] = df.apply(split_name_and_dosage, axis=1)

    # Drop rows with missing values in either column
    df = df.dropna(subset=["name", "code"])

    # Extract aic6 as the first 6 digits of the code (as string, padded if needed)
    df["aic6"] = df["code"].astype(str).str.zfill(9).str[:6]

    if aic:
        return df[["name", "code", "aic6"]].itertuples(index=False, name=None)

    # Return as set of tuples (name, aic6)
    return set(df[["name", "aic6"]].itertuples(index=False, name=None))


def download_leaflets_for_drugs(
    drugs_to_process: list,
    base_dir: str = "data/leaflets/raw",
    failed_csv: str = "data/leaflets/failed_downloads.csv",
) -> None:
    keys = ["name", "aic6", "failed"]
    file_exists = os.path.exists(failed_csv)
    # Open the CSV once in append mode
    with open(failed_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        if not file_exists:
            writer.writeheader()
        for drug_name, aic_code in tqdm(drugs_to_process, desc="Downloading leaflets"):
            print(f"Downloading leaflets for {drug_name} with AIC code {aic_code}")
            fail_reason = save_leaflets(drug_name, aic_code, base_dir=base_dir)
            if fail_reason:
                writer.writerow(
                    {"name": drug_name, "aic6": aic_code, "failed": fail_reason}
                )
                f.flush()  # Ensure it's written to disk immediately
            print(
                f"Finished downloading leaflets for {drug_name} with AIC code {aic_code}"
            )
            print("-" * 40)
    print(f"Failed downloads appended to {failed_csv}")


if __name__ == "__main__":

    # Path to your Excel file
    drugs_file = "/home/francesca/Desktop/DS Bootcamp/portfolio_project/rxassist-ai/data/leaflets/estrazione_farmaci.xlsx"

    # Read the Excel file and extract the drug names (adjust column name if needed)
    drugs = parse_drugs_file(drugs_file)

    # Download leaflets for the drugs
    download_leaflets_for_drugs(list(drugs))

import requests
import os
from pathlib import Path
from typing import List, Optional, Dict, Any


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


def save_leaflets(drug_name: str, base_dir: str = "data/raw") -> None:
    """
    Download all available leaflets (FI and RCP) for a given drug.

    Args:
        drug_name (str): The drug name to process.
        base_dir (str): Directory to save the PDFs.
    """
    # Create a subdirectory with the drug name (uppercased and spaces replaced)
    sanitized_name = drug_name.strip().replace(" ", "_").upper()
    save_dir = os.path.join(base_dir, sanitized_name)

    page = 0
    while True:
        data = get_drug_data(drug_name, page=page)
        content = data.get("data", {}).get("content", [])

        if not content:
            if page == 0:
                print(f"No data found for {drug_name}.")
            break

        for result in content:
            codice_sis = result["medicinale"]["codiceSis"]
            aic6 = result["medicinale"]["aic6"]

            urls = {
                "FI": f"https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/{codice_sis}/farmaci/{aic6}/stampati?ts=FI",
                "RCP": f"https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/{codice_sis}/farmaci/{aic6}/stampati?ts=RCP",
            }

            for kind, url in urls.items():
                filename = f"{save_dir}/{kind}_{str(codice_sis).zfill(6)}_{str(aic6).zfill(6)}.pdf"
                try:
                    download_pdf(url, filename)
                    print(f"Downloaded: {filename}")
                except requests.HTTPError as e:
                    print(f"Failed to download {kind} for {aic6}: {e}")

        page += 1  # Go to next page


def download_leaflets_for_drugs(
    drugs_to_process: List[str], base_dir: str = "data/raw"
) -> None:
    """
    Download all available leaflets for a list of drugs.

    Args:
        drugs_to_process (List[str]): List of drug names to process.
        base_dir (str): Directory to save the PDFs.
    """
    for drug in drugs_to_process:
        save_leaflets(drug, base_dir=base_dir)


if __name__ == "__main__":
    drugs_to_process = ["CITALOPRAM", "AZITROMICINA"]
    download_leaflets_for_drugs(drugs_to_process)

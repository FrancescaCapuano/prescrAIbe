import pandas as pd
from pathlib import Path

drugs = pd.read_excel("data/leaflets/estrazione_farmaci.xlsx")
drugs["code"] = drugs["code"].astype(str).str.zfill(9)  # Ensure AIC codes are 9 digits

# Select only the drugs for which a leaflet exists
leaflets_processed_path = "data/leaflets/processed"
leaflet_files = [
    f.stem.split("_")[-1] for f in Path(leaflets_processed_path).glob("*.md")
]
drugs = drugs[drugs["code"].isin(leaflet_files)]


# save the filtered drugs to a new Excel file
output_path = "data/leaflets/estrazione_farmaci_downloaded.xlsx"
drugs.to_excel(output_path, index=False)

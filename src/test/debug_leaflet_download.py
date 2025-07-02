import pandas as pd
import pdb
import os


# Read the leaflets
leaflet_file = "../../data/leaflets/estrazione_farmaci.xlsx"
leaflet_df = pd.read_excel(leaflet_file)
leaflet_df["code"] = leaflet_df["code"].astype(str).str[:-3]
leaflet_df["code"] = leaflet_df["code"].str.zfill(6)

# Read the failed downloads
failed_downloads_file = "../../data/leaflets/failed_downloads.csv"
failed_downloads_df = pd.read_csv(failed_downloads_file)
failed_downloads_df["aic6"] = failed_downloads_df["aic6"].astype(str)
failed_downloads_df["aic6"] = failed_downloads_df["aic6"].str.zfill(6)

# Select only the leaflets for which the download was successful
# leaflet_df = leaflet_df[~leaflet_df["code"].isin(failed_downloads_df["aic6"])]
unique_aic6_codes = leaflet_df["code"].unique()
print("Number of unique AIC6 codes:", len(unique_aic6_codes))

# Read all raw leaflet files
raw_dir = "../../data/leaflets/raw"
leaflet_files = [f for f in os.listdir(raw_dir) if f.endswith(".pdf")]
print(f"Found {len(leaflet_files)} raw leaflet files.")

# all codes have length 6, they CAN start with 00
aic6_codes_from_pdfs = [f.split("_")[-1].split(".")[0] for f in leaflet_files]
unique_aic6_codes_from_pdfs = set(aic6_codes_from_pdfs)
print(
    "Number of unique AIC6 codes from PDF filenames:", len(unique_aic6_codes_from_pdfs)
)

# Check if, for each drug, there is a leaflet
miss = 0
for c in unique_aic6_codes:
    if c not in aic6_codes_from_pdfs:
        miss += 1
        print(f"Code {c} is missing from PDF filenames.")
print(f"Number of missing codes: {miss}")

miss = 0
for index, row in leaflet_df.iterrows():
    aic6_code = row["code"]

    # Check if the code exists in the PDF filenames
    if aic6_code not in aic6_codes_from_pdfs:
        miss += 1
        print(f"Code {aic6_code} is missing from PDF filenames.")
print(f"Number of missing codes in DataFrame: {miss}")

# Check if, for each code from the PDFs, there is a corresponding unique AIC6 code
for c in aic6_codes_from_pdfs:
    if c not in unique_aic6_codes:
        print(f"Code {c} is not in the unique AIC6 codes.")

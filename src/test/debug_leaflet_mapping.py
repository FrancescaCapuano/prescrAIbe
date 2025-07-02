import pandas as pd

# Read the drugs leaflet mapping file
drugs_leaflet_mapping = pd.read_csv("../../data/leaflets/drugs_leaflet_mapping.csv")

# Tot rows should be equal to rows in estrazione_farmaci.xlsx
print(f"✅ Number of rows in drugs_leaflet_mapping: {len(drugs_leaflet_mapping)}")

# Read the failed downloads file
failed_downloads_df = pd.read_csv("../../data/leaflets/failed_downloads.csv")

# exclude drugs from drugs_leaflet_mapping that are in failed_downloads_df
failed_aic6 = failed_downloads_df["aic6"].unique()
print(f"✅ Number of failed drugs: {failed_downloads_df.shape[0]}")
print(f"✅ Number of failed aic6: {len(failed_aic6)}")

# Filter out failed aic6 from drugs_leaflet_mapping
filtered_drugs_leaflet_mapping = drugs_leaflet_mapping[
    ~drugs_leaflet_mapping["aic6"].isin(failed_aic6)
]
# Print number of rows after filtering
print(
    f"✅ Number of rows after filtering failed aic6: {len(filtered_drugs_leaflet_mapping)}"
)

# how many unique aic6 are left after filtering?
unique_aic6_after_filtering = filtered_drugs_leaflet_mapping["aic6"].nunique()
print(f"✅ Unique aic6 after filtering: {unique_aic6_after_filtering}")

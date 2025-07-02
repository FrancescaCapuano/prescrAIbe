# Read "../data/leaflets/failed_downloads.csv" file and map failed downloads to AICs
import pandas as pd
from pathlib import Path

failed_downloads_path = Path("../../data/leaflets/failed_downloads.csv")
failed_downloads_df = pd.read_csv(failed_downloads_path)

# Read estrazione_farmaci.xlsx file
drugs_file_path = Path("../../data/leaflets/estrazione_farmaci.xlsx")
drugs_df = pd.read_excel(drugs_file_path)

# Split "name" by "*", assign first part to "name", second part to "dosage"
drugs_df[["name", "dosage"]] = drugs_df["name"].str.split("*", n=1, expand=True)
print("Drugs DataFrame after splitting 'name':")
print(drugs_df.head())

# Add "code" to failed_downloads_df by matching "name" in drugs_df
failed_downloads_df["code"] = failed_downloads_df["name"].map(
    drugs_df.set_index("name")["code"]
)

# Print the updated failed_downloads_df
print("\nFailed Downloads DataFrame after mapping codes:")
print(failed_downloads_df.head())

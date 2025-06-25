import pandas as pd
import numpy as np

# Path to the Excel file containing drug data
drugs_file = "data/leaflets/estrazione_farmaci.xlsx"

# Read the Excel file into a DataFrame
df = pd.read_excel(drugs_file)

# Set seed for reproducibility
np.random.seed(42)  # You can use any number

# Randomly sample n rows
n = 40  # Change this to your desired number of rows
df_sample = df.sample(n=n, random_state=42)

print(f"Original dataset: {len(df)} rows")
print(f"Sampled dataset: {len(df_sample)} rows")

# Optionally save the sample to a new file
df_sample.to_excel("data/leaflets/random_sample.xlsx", index=False)
print(f"Sample saved to: data/leaflets/random_sample.xlsx")

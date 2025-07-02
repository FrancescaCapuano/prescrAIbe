# Read ICD-11 JSON file
import json


with open("../../data/ICD-codes/icd11_vectordb_base.json", "r", encoding="utf-8") as f:
    icd11_data = json.load(f)

# Exclude entries where the code starts with irrelevant prefixes
irrelevant_prefixes = ["M", "N", "P", "Q", "R", "V", "X"]
icd11_data = [
    entry
    for entry in icd11_data
    if not any(entry["code"].startswith(prefix) for prefix in irrelevant_prefixes)
]

# Exclude the "description" field
for entry in icd11_data:
    if "description" in entry:
        del entry["description"]

# Save the filtered data to a new JSON file
output_file = "../../data/ICD-codes/icd11_vectordb_base_compressed.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(icd11_data, f, ensure_ascii=False, indent=4)

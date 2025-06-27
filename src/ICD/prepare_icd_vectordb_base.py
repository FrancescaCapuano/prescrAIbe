import json
from pathlib import Path


def create_description(item):
    """Create a comprehensive description by concatenating relevant fields."""
    parts = []

    # Add main fields
    for field in ["title", "fully_specified_name", "definition"]:
        if item.get(field):
            parts.append(item[field])

    # Add inclusions and all_labels as comma-separated strings
    if item.get("inclusions"):
        parts.append(", ".join(item["inclusions"]))

    if item.get("all_labels"):
        parts.append(", ".join(item["all_labels"]))

    # Add parent information
    for parent in item.get("parent_info", []):
        if parent.get("title"):
            parts.append(parent["title"])
        if parent.get("definition"):
            parts.append(parent["definition"])

    return " ".join(filter(None, parts))


def process_icd11_data():
    """Process ICD-11 database and create vectordb base file."""

    # File paths (relative to src/ICD directory)
    input_file = Path("../../data/ICD-codes/icd11_database.json")
    output_file = Path("../../data/ICD-codes/icd11_vectordb_base.json")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load input data
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Transform data
    transformed_data = [
        {
            "code": item["code"],
            "name": item["title"],
            "description": create_description(item),
            "url": item["browser_url"],
        }
        for item in data
    ]

    # Save output
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transformed_data, f, indent=2, ensure_ascii=False)

    print(f"Processed {len(transformed_data)} items")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    process_icd11_data()

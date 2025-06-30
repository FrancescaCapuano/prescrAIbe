import json
from pathlib import Path


class ICD11VectorDBPreparer:
    def __init__(
        self,
        input_file="data/ICD-codes/icd11_database.json",
        output_file="data/ICD-codes/icd11_vectordb_base.json",
    ):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
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

    def process(self):
        """Process ICD-11 database and create vectordb base file."""
        # Load input data
        with open(self.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Transform data
        transformed_data = [
            {
                "code": item["code"],
                "name": item["title"],
                "description": self.create_description(item),
                "url": item["browser_url"],
            }
            for item in data
        ]

        # Save output
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(transformed_data, f, indent=2, ensure_ascii=False)

        print(f"Processed {len(transformed_data)} items")
        print(f"Output saved to: {self.output_file}")


if __name__ == "__main__":
    preparer = ICD11VectorDBPreparer()
    preparer.process()

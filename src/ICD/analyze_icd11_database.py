import json
import os
from collections import Counter


def analyze_icd_database():
    # Get the correct path (go up to project root, then to data folder)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    json_path = os.path.join(project_root, "data", "ICD-codes", "icd11_database.json")
    output_path = os.path.join(script_dir, "icd_analysis_results.txt")

    # Load the JSON data
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Prepare results
    results = []

    # Count total objects
    total_count = len(data)
    results.append(f"Total code objects: {total_count}")
    print(f"Total code objects: {total_count}")

    # Count by last parent
    parent_counts = Counter()
    codes = []

    for item in data:
        codes.append(item["code"])

        # Get last parent (most specific category)
        if item["parent_info"]:
            last_parent = item["parent_info"][-1]["title"]
            parent_counts[last_parent] += 1
        else:
            parent_counts["No Parent"] += 1

    # Display counts by parent
    results.append("\nCounts by last parent category:")
    print("\nCounts by last parent category:")
    for parent, count in parent_counts.most_common():
        line = f"  {parent}: {count}"
        results.append(line)
        print(line)

    # Check for duplicate codes
    code_counts = Counter(codes)
    duplicates = [code for code, count in code_counts.items() if count > 1]

    if duplicates:
        duplicate_msg = f"\nDuplicate codes found: {duplicates}"
        results.append(duplicate_msg)
        print(duplicate_msg)
    else:
        no_duplicate_msg = "\nNo duplicate codes found."
        results.append(no_duplicate_msg)
        print(no_duplicate_msg)

    # Write results to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    analyze_icd_database()

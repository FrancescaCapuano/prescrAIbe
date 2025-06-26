import os
import openai
import json
import re
from dotenv import load_dotenv
from datetime import datetime


def parse_table_to_json(table_text):
    """Parse the markdown table from GPT response into a JSON structure."""
    lines = table_text.strip().split("\n")

    # Find the header line (first line with |)
    header_line = None
    data_lines = []

    for i, line in enumerate(lines):
        if "|" in line and "Medical Condition Name" in line:
            header_line = line
            # Skip the separator line (usually contains dashes)
            data_start = (
                i + 2 if i + 1 < len(lines) and "---" in lines[i + 1] else i + 1
            )
            data_lines = lines[data_start:]
            break

    if not header_line:
        print("Warning: Could not find table header")
        return None

    # Extract headers
    headers = [h.strip() for h in header_line.split("|") if h.strip()]

    # Extract data rows
    pathologies = []
    for line in data_lines:
        if "|" in line and line.strip():
            row = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(row) == len(headers):  # Only add complete rows
                pathology = {}
                for i, header in enumerate(headers):
                    pathology[header] = row[i]
                pathologies.append(pathology)

    if not pathologies:
        print("Warning: No data rows found")
        return None

    return pathologies


def extract_clinical_pathologies():
    """Extract clinical pathologies from medication package insert using ChatGPT API."""

    print("Starting extraction process...")

    # Load environment variables
    print("Loading environment variables...")
    load_dotenv("../.env")

    # Check if API key exists
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return
    print("API key loaded successfully")

    # Initialize OpenAI client
    print("Initializing OpenAI client...")
    client = openai.OpenAI(api_key=api_key)

    # Read the data file
    print("Reading data file...")
    try:
        with open("../data/test_LLM_prompt.md", "r", encoding="utf-8") as file:
            package_insert_data = file.read()
        print(f"File read successfully. Length: {len(package_insert_data)} characters")
    except FileNotFoundError:
        print("Error: ../data/test_LLM_prompt.md not found")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Construct the prompt
    prompt = f"""Extract all pre-existing clinical pathologies that could lead to side effects when taking this medication. Exclude conditions caused by the medication itself.

For each pathology, provide:
1. Medical condition name
2. Specific condition text (Part 2) - the exact text fragment as it appears in the leaflet
3. Warning introduction (Part 1) - only if the condition was part of a list following an introductory phrase like "Assuma questo medicinale con cautela e informi il medico se:" (leave empty if the warning is standalone)

Output as table with columns: "Medical Condition Name" | "Specific Condition Text (Part 2)" | "Warning Introduction (Part 1)"

Use only actual text from data. Pay attention to warning structures where multiple conditions follow an introductory phrase.

Data:
{package_insert_data}"""

    try:
        print("Making API call to OpenAI... (this may take 30+ seconds)")

        # Make API call
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        # Extract response
        result = response.choices[0].message.content
        print("\nClinical Pathologies Extraction Results:")
        print("=" * 50)
        print(result)

        # Parse the table and save to JSON
        print("\nParsing results and saving to JSON...")
        pathologies = parse_table_to_json(result)

        if pathologies is not None:
            # Create output directory if it doesn't exist
            output_dir = "../data/pathologies_leaflet"
            os.makedirs(output_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"{output_dir}/clinical_pathologies_{timestamp}.json"

            # Create the complete JSON structure
            output_data = {
                "extraction_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": "gpt-4o-mini",
                    "source_file": "../data/test_LLM_prompt.md",
                    "total_pathologies": len(pathologies),
                },
                "clinical_pathologies": pathologies,
            }

            # Save to JSON with proper formatting
            with open(json_filename, "w", encoding="utf-8") as json_file:
                json.dump(output_data, json_file, indent=2, ensure_ascii=False)

            print(f"Results saved to: {json_filename}")
            print(f"Number of pathologies extracted: {len(pathologies)}")

            # Display first few entries as confirmation
            print("\nFirst few pathologies in the JSON:")
            for i, pathology in enumerate(pathologies[:3]):
                print(f"{i+1}. {pathology.get('Medical Condition Name', 'Unknown')}")

            return result, json_filename
        else:
            print("Error: Could not parse the table format")
            return result, None

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None, None


def main():
    """Main function to run the extraction and save results."""
    result, json_file = extract_clinical_pathologies()

    if json_file:
        print(f"\n✅ Process completed successfully!")
        print(f"📄 Raw results displayed above")
        print(f"💾 JSON file saved: {json_file}")
    else:
        print("\n❌ Process completed but JSON export failed")


if __name__ == "__main__":
    main()

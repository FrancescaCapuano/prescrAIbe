## python src/llm_translation/llm_translation.py

import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

print("Environment variables loaded.")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
print("OpenAI client initialized.")


def translate_warning(warning_text):
    """Translate warning text to English using OpenAI API."""
    try:
        print(f"\nTranslating warning: {warning_text}")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate the following medical warning to English. Keep the translation accurate and professional.",
                },
                {"role": "user", "content": warning_text},
            ],
            temperature=0,
        )
        translation = response.choices[0].message.content.strip()
        print(f"Translation completed: {translation}")
        return translation
    except Exception as e:
        print(f"Error during translation: {e}")
        return warning_text


def process_interaction_matrix():
    # Define file paths
    input_file = (
        Path(__file__).parent.parent.parent
        / "data/interaction_matrix/interaction_matrix.json"
    )
    output_file = (
        Path(__file__).parent.parent.parent
        / "data/interaction_matrix/interaction_matrix_translated.json"
    )

    print(f"\nReading input file from: {input_file}")

    try:
        # Read the original JSON file
        with open(input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)

        # Load existing translations if they exist
        existing_translations = {}
        if output_file.exists():
            with open(output_file, "r", encoding="utf-8") as f:
                existing_translations = json.load(f)

        print(f"Successfully loaded input JSON file with {len(input_data)} entries")

        # Counter for progress tracking
        total_warnings = 0
        translated_warnings = 0

        # New structure for the output data
        output_data = existing_translations.copy()

        # Process each entry and its sub-items
        for key, items in input_data.items():
            if not isinstance(items, list):
                continue

            warnings_list = []
            needs_update = False

            for item in items:
                if "warning" not in item:
                    continue

                total_warnings += 1
                warning_text = item["warning"]

                # Check if this warning is already translated
                warning_already_translated = False
                if key in existing_translations:
                    for existing_warning in existing_translations[key]:
                        if existing_warning["warning"] == warning_text:
                            warnings_list.append(existing_warning)
                            warning_already_translated = True
                            break

                if not warning_already_translated:
                    print(f"Processing new warning for {key}")
                    warning_eng = translate_warning(warning_text)
                    warnings_list.append(
                        {"warning": warning_text, "warning_eng": warning_eng}
                    )
                    translated_warnings += 1
                    needs_update = True

            if warnings_list:
                output_data[key] = warnings_list
                # Save progress after each key is processed
                if needs_update:
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(output_data, f, ensure_ascii=False, indent=2)

        print("\nTranslation summary:")
        print(f"Total warnings processed: {total_warnings}")
        print(f"Newly translated warnings: {translated_warnings}")
        print(f"Output saved to: {output_file}")

    except Exception as e:
        print(f"Error processing file: {e}")


if __name__ == "__main__":
    print("Starting translation process...")
    process_interaction_matrix()
    print("Process completed.")

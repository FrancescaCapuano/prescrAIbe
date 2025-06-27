import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
import openai
from dotenv import load_dotenv
from pydantic import BaseModel
from tqdm import tqdm

# Load environment variables - fix the path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
env_path = project_root / ".env"

# Load the .env file
load_dotenv(env_path)

# Constants
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0
API_KEY = os.getenv("OPENAI_API_KEY")


class Contraindication(BaseModel):
    """Pydantic model for a single contraindication."""

    context: str
    pretext: str
    warning_ita: str
    context_eng: str


class Contraindications(BaseModel):
    """Pydantic model for a list of contraindications."""

    contraindication: list[Contraindication]


def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
):
    """Call OpenAI API with the given prompt and system prompt."""
    if not API_KEY:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        return None

    client = openai.OpenAI(api_key=API_KEY)

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # FIXED: Use the correct OpenAI API method
        response = client.beta.chat.completions.parse(
            model=model,
            messages=messages,  # FIXED: Use 'messages' not 'input'
            temperature=temperature,
            response_format=Contraindications,  # FIXED: Use 'response_format' not 'text_format'
        )

        return response.choices[0].message.parsed

    except Exception as e:
        print(f"❌ Error calling OpenAI API: {e}")
        return None


def build_prompt(prompt_template: str, leaflet_section: str) -> str:
    """Build the complete prompt using template and leaflet section."""
    return prompt_template.format(leaflet_contraindications=leaflet_section)


def load_progress(progress_file: str) -> dict:
    """Load existing progress from file."""
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
            return progress
        except Exception as e:
            print(f"⚠️  Error loading progress file: {e}")
            return {"processed_files": [], "contraindications": [], "stats": {}}
    return {"processed_files": [], "contraindications": [], "stats": {}}


def save_progress(progress_data: dict, progress_file: str, output_file: str):
    """Save current progress to both progress file and output file."""
    # Save progress state
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

    # Save current contraindications to output file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(progress_data["contraindications"], f, indent=2, ensure_ascii=False)


def process_single_leaflet(
    filename: str,
    leaflet_sections_dir: str,
    user_prompt_template: str,
    system_prompt: str,
    model: str,
    temperature: float,
):
    """Process a single leaflet file and extract contraindications."""
    leaflet_file_path = os.path.join(leaflet_sections_dir, filename)

    # Read leaflet section
    with open(leaflet_file_path, "r", encoding="utf-8") as file:
        leaflet_section = file.read()

    # Build and send prompt
    user_prompt = build_prompt(user_prompt_template, leaflet_section)

    response = call_llm(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
    )

    return response


def convert_response_to_json_format(response, aic: str, url: str) -> dict:
    """Convert Pydantic response to JSON format."""
    if not response or not hasattr(response, "contraindication"):
        return {"aic": aic, "url": url, "contraindications": []}

    contraindications_list = []
    total_count = len(response.contraindication)

    for i, contraindication in enumerate(response.contraindication, 1):
        formatted_item = {
            "id": i,
            "context": contraindication.context,
            "pretext": contraindication.pretext,
            "warning_ita": contraindication.warning_ita,
            "context_eng": contraindication.context_eng,
            "extraction_timestamp": datetime.now().isoformat(),
        }
        contraindications_list.append(formatted_item)

    return {
        "aic": aic,
        "url": url,
        "contraindications": contraindications_list,
        "extraction_stats": {
            "total_extracted": total_count,
        },
    }


def extract_all_contraindications(
    system_prompt_path: str = "data/prompts/system_prompt.txt",
    user_prompt_path: str = "data/prompts/user_prompt_template.txt",
    leaflet_sections_dir: str = "data/leaflets/sections",
    output_file: str = "data/contraindications/all_contraindications.json",
    progress_file: str = "data/contraindications/extraction_progress.json",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    test_mode: bool = True,
    test_count: int = 5,
) -> None:
    """Extract contraindications from all leaflets with progress tracking and resume capability."""

    print("🚀 Starting contraindication extraction with progress tracking")

    # Read prompts
    with open(user_prompt_path, "r", encoding="utf-8") as file:
        user_prompt_template = file.read()
    with open(system_prompt_path, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    # Create output directories
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    os.makedirs(os.path.dirname(progress_file), exist_ok=True)

    # Load existing progress
    progress_data = load_progress(progress_file)
    processed_files = set(progress_data["processed_files"])
    all_contraindications = progress_data["contraindications"]

    # Get all markdown files
    md_files = [f for f in os.listdir(leaflet_sections_dir) if f.endswith(".md")]

    # Filter out already processed files
    remaining_files = [f for f in md_files if f not in processed_files]

    if test_mode:
        remaining_files = remaining_files[:test_count]
        print(f"📋 TEST MODE: Processing {len(remaining_files)} files")
    else:
        print(f"📋 FULL MODE: Processing {len(remaining_files)} remaining files")

    if len(processed_files) > 0:
        print(f"📂 Resuming: {len(processed_files)} files already processed")
        print(f"📊 Current contraindications: {len(all_contraindications)}")

    if not remaining_files:
        print("✅ All files already processed!")
        return

    # Statistics tracking
    session_stats = {
        "successful_extractions": 0,
        "failed_extractions": 0,
        "total_extracted": 0,
        "failed_files": [],
    }

    # Process remaining files with progress bar
    with tqdm(remaining_files, desc="Processing leaflets", unit="file") as pbar:
        for filename in pbar:
            pbar.set_description(f"Processing {filename[:30]}...")

            try:
                # Extract metadata
                aic = extract_aic_from_filename(filename)
                aic6 = aic[:6]
                codice_sis = extract_sis_from_filename(filename)
                url = generate_url(aic6, codice_sis)

                # Process the leaflet
                response = process_single_leaflet(
                    filename,
                    leaflet_sections_dir,
                    user_prompt_template,
                    system_prompt,
                    model,
                    temperature,
                )

                if response is None:
                    session_stats["failed_extractions"] += 1
                    session_stats["failed_files"].append(filename)
                    pbar.set_postfix({"❌": "API Failed"})
                    tqdm.write(f"❌ {filename}: API Failed")
                    continue

                # Count total extracted
                file_extracted = 0
                if hasattr(response, "contraindication"):
                    file_extracted = len(response.contraindication)
                    session_stats["total_extracted"] += file_extracted

                # Convert to JSON format
                json_entry = convert_response_to_json_format(response, aic, url)

                # Add entries
                if json_entry["contraindications"]:
                    all_contraindications.append(json_entry)
                    session_stats["successful_extractions"] += 1

                    # Print per-file extraction count
                    tqdm.write(
                        f"📄 {filename}: Extracted {file_extracted} contraindications"
                    )

                    pbar.set_postfix(
                        {
                            "📊": f"{file_extracted} extracted",
                            "💾": f"{len(all_contraindications)} total entries",
                        }
                    )
                else:
                    session_stats["successful_extractions"] += 1
                    tqdm.write(f"📄 {filename}: No contraindications found")
                    pbar.set_postfix({"ℹ️": "No contraindications"})

                # Mark as processed and save progress
                processed_files.add(filename)
                progress_data = {
                    "processed_files": list(processed_files),
                    "contraindications": all_contraindications,
                    "stats": {
                        "total_processed": len(processed_files),
                        "total_entries": len(all_contraindications),
                        "session_stats": session_stats,
                        "last_updated": datetime.now().isoformat(),
                    },
                }

                # Save progress after each file
                save_progress(progress_data, progress_file, output_file)

            except Exception as e:
                session_stats["failed_extractions"] += 1
                session_stats["failed_files"].append(filename)
                pbar.set_postfix({"❌": f"Error: {str(e)[:20]}"})
                tqdm.write(f"❌ {filename}: Error - {e}")

    # Calculate final statistics
    total_contraindications = sum(
        len(entry["contraindications"]) for entry in all_contraindications
    )

    # Print detailed final summary
    print(f"\n" + "=" * 80)
    print(f"🎯 EXTRACTION SUMMARY")
    print(f"=" * 80)

    print(f"\n📊 SESSION STATISTICS:")
    print(f"Files processed this session: {len(remaining_files)}")
    print(f"Successful extractions: {session_stats['successful_extractions']}")
    print(f"Failed extractions: {session_stats['failed_extractions']}")
    print(f"Total extracted by LLM: {session_stats['total_extracted']}")

    print(f"\n📋 OVERALL DATABASE STATISTICS:")
    print(f"Total files processed: {len(processed_files)}")
    print(f"Total entries with contraindications: {len(all_contraindications)}")
    print(f"Total contraindications in database: {total_contraindications}")

    print(f"\n💾 FILES:")
    print(f"Output file: {output_file}")
    print(f"Progress file: {progress_file}")

    if session_stats["failed_files"]:
        print(f"\n❌ Failed files this session:")
        for failed_file in session_stats["failed_files"]:
            print(f"  - {failed_file}")

    # Final save
    save_progress(progress_data, progress_file, output_file)
    print(f"\n✅ Progress saved! You can resume by running the script again.")

    # Highlight the key metric
    print(f"\n" + "=" * 80)
    print(f"🎯 TOTAL CONTRAINDICATIONS EXTRACTED: {total_contraindications}")
    print(f"   From {len(all_contraindications)} entries")
    print(f"=" * 80)


def extract_aic_from_filename(filename: str) -> str:
    """Extract AIC code from filename."""
    return filename.split("_")[-1].split(".")[0]


def extract_sis_from_filename(filename: str) -> str:
    """Extract SIS code from filename."""
    return filename.split("_")[-2][2:]


def generate_url(aic6: str, codice_sis: str) -> str:
    """Generate the PDF URL from AIC and SIS codes."""
    return f"https://api.aifa.gov.it/aifa-bdf-eif-be/1.0.0/organizzazione/{codice_sis}/farmaci/{aic6}/stampati?ts=FI"


# Update your main section
if __name__ == "__main__":
    import sys

    # Check command line arguments
    test_mode = "--full" not in sys.argv
    test_count = 5

    if "--count" in sys.argv:
        try:
            count_index = sys.argv.index("--count") + 1
            test_count = int(sys.argv[count_index])
        except (IndexError, ValueError):
            print("⚠️  Invalid --count argument, using default 5")

    mode_str = f"TEST ({test_count} files)" if test_mode else "FULL"
    print(f"🎯 Running in {mode_str} mode")
    print("💡 Use --full for full processing, --count N to set test count")

    extract_all_contraindications(
        system_prompt_path="data/prompts/system_prompt.txt",
        user_prompt_path="data/prompts/user_prompt_template.txt",
        leaflet_sections_dir="data/leaflets/sections",
        output_file="data/contraindications/all_contraindications.json",
        progress_file="data/contraindications/extraction_progress.json",
        test_mode=test_mode,
        test_count=test_count,
    )

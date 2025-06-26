import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import pdb

import openai
from dotenv import load_dotenv
from pydantic import BaseModel

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

    contraindication: str
    medical_condition_name_part_2: str
    warning_introduction_part_1: str


class Contraindications(BaseModel):
    """Pydantic model for a list of contraindications."""

    contraindication: list[Contraindication]


def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
):
    """
    Call OpenAI API with the given prompt and system prompt.

    Returns:
        API response content or None if failed.
    """
    if not API_KEY:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        return None

    client = openai.OpenAI(api_key=API_KEY)

    try:
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        response = client.responses.parse(
            model=model,
            input=messages,
            temperature=temperature,
            text_format=Contraindications,
        )
        return response.output_parsed
    except Exception as e:
        print(f"❌ Error calling OpenAI API: {e}")
        return None


def build_prompt(prompt_template: str, leaflet_section: str) -> str:
    """Build the complete prompt using template and leaflet section."""
    return prompt_template.format(leaflet_contraindications=leaflet_section)


def save_contraindications(
    contraindications: List[dict],
    filename: str,
    output_dir: str,
    model: str,
    temperature: float,
    source_file: str,
    source_path: str,
    user_prompt_path: str,
    system_prompt_path: str,
) -> str:
    """Save contraindications with metadata to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = filename.replace(".md", "")
    json_filename = f"{output_dir}/contraindications_{base_filename}_{timestamp}.json"

    output_data = {
        "extraction_metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "temperature": temperature,
            "source_file": source_file,
            "source_path": source_path,
            "total_contraindications": len(contraindications),
            "user_prompt_template": user_prompt_path,
            "system_prompt_template": system_prompt_path,
        },
        "contraindications": contraindications,
    }

    with open(json_filename, "w", encoding="utf-8") as json_file:
        json.dump(output_data, json_file, indent=2, ensure_ascii=False)

    return json_filename


def process_single_leaflet(
    filename: str,
    leaflet_sections_dir: str,
    user_prompt_template: str,
    system_prompt: str,
    model: str,
    temperature: float,
    save_json: bool,
    output_dir: str,
    user_prompt_path: str,
    system_prompt_path: str,
) -> bool:
    """
    Process a single leaflet file and extract contraindications.

    Returns:
        True if successful, False otherwise.
    """
    leaflet_file_path = os.path.join(leaflet_sections_dir, filename)

    try:
        print(f"🔍 Processing leaflet section: {filename}")

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

        if response is None:
            print(f"❌ Failed to get response for {filename}")
            return False

        # Handle the Contraindications object properly
        if hasattr(response, "contraindication") and isinstance(
            response.contraindication, list
        ):
            # response is a Contraindications object with a list of Contraindication objects
            contraindications_list = [c.dict() for c in response.contraindication]
        elif hasattr(response, "dict"):
            # response is a single Contraindication object
            contraindications_list = [response.dict()]
        elif isinstance(response, list):
            # response is already a list of objects
            contraindications_list = [
                c.dict() if hasattr(c, "dict") else c for c in response
            ]
        else:
            # fallback - treat as single item
            contraindications_list = [response]

        # Save results with metadata
        if save_json and contraindications_list:
            json_filename = save_contraindications(
                contraindications_list,
                filename,
                output_dir,
                model,
                temperature,
                filename,
                leaflet_file_path,
                user_prompt_path,
                system_prompt_path,
            )
            print(
                f"💾 Saved {len(contraindications_list)} contraindications to: {json_filename}"
            )

        # Display results - now showing actual count
        print(f"✅ Extracted {len(contraindications_list)} contraindications:")
        for i, item in enumerate(contraindications_list, 1):
            contraindication_text = (
                item.get("contraindication", str(item))
                if isinstance(item, dict)
                else str(item)
            )
            print(f"  {i}. {contraindication_text}")

        print("-" * 80)
        return True

    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")
        return False


def extract_contraindications(
    system_prompt_path: str = "../../data/prompts/system_prompt.txt",
    user_prompt_path: str = "../../data/prompts/user_prompt_template.txt",
    leaflet_sections_dir: str = "../../data/leaflet/sections",
    output_dir: str = "../../data/extracted_contraindications",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    save_json: bool = True,
) -> None:
    """Extract contraindications from leaflet sections and save with metadata."""

    # Setup
    if save_json:
        os.makedirs(output_dir, exist_ok=True)

    # Read both prompts
    with open(user_prompt_path, "r", encoding="utf-8") as file:
        user_prompt_template = file.read()

    with open(system_prompt_path, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    # Process files
    md_files = [f for f in os.listdir(leaflet_sections_dir) if f.endswith(".md")]
    total_processed = len(md_files)
    successful_extractions = 0
    failed_extractions = []

    for filename in md_files:
        success = process_single_leaflet(
            filename,
            leaflet_sections_dir,
            user_prompt_template,
            system_prompt,  # Pass system prompt
            model,
            temperature,
            save_json,
            output_dir,
            user_prompt_path,
            system_prompt_path,
        )

        if success:
            successful_extractions += 1
        else:
            failed_extractions.append(filename)

    # Print summary
    print(f"\n📊 EXTRACTION SUMMARY:")
    print(f"=" * 50)
    print(f"Total files processed: {total_processed}")
    print(f"Successful extractions: {successful_extractions}")
    print(f"Failed extractions: {len(failed_extractions)}")

    if failed_extractions:
        print(f"\n❌ Failed files:")
        for failed_file in failed_extractions:
            print(f"  - {failed_file}")

    if save_json:
        print(f"\n💾 Results saved to: {output_dir}")

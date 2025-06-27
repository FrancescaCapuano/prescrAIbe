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

    context: str
    pretext: str
    warning_ita: str
    warning_eng: str


class Contraindications(BaseModel):
    """Pydantic model for a list of contraindications."""

    contraindication: list[Contraindication]


def context_is_in_leaflet(context, leaflet):
    """
    Check if a given context is present in the leaflet text.
    Uses flexible matching to handle truncation and formatting differences.
    """
    context_lower = context.lower().strip()
    leaflet_lower = leaflet.lower()

    # Remove quotes and normalize
    context_clean = context_lower.replace("'", "").replace('"', "")

    # CRITICAL: Normalize whitespace and newlines PROPERLY
    import re

    context_normalized = re.sub(r"\s+", " ", context_clean).strip()
    leaflet_normalized = re.sub(r"\s+", " ", leaflet_lower).strip()

    # IMPROVED: Remove problematic Unicode characters more aggressively
    # Remove the specific problematic character \uf0fc and similar private use area chars
    context_final = re.sub(
        r"[\uf000-\uf8ff]", "", context_normalized
    )  # Private Use Area
    context_final = re.sub(
        r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", context_final
    )  # Zero-width spaces
    context_final = re.sub(
        r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]", " ", context_final
    )  # Various spaces
    context_final = re.sub(r"\s+", " ", context_final).strip()

    leaflet_final = re.sub(
        r"[\uf000-\uf8ff]", "", leaflet_normalized
    )  # Private Use Area
    leaflet_final = re.sub(
        r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", leaflet_final
    )  # Zero-width spaces
    leaflet_final = re.sub(
        r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]", " ", leaflet_final
    )  # Various spaces
    leaflet_final = re.sub(r"\s+", " ", leaflet_final).strip()

    # DEBUG: Show the cleaning result for enoxaparina
    if "enoxaparina" in context_normalized:
        print(f"\n🔧 AFTER CLEANING:")
        print(f"Context final: '{context_final}'")
        if "enoxaparina" in leaflet_final:
            enox_pos = leaflet_final.find("enoxaparina")
            leaflet_excerpt_clean = leaflet_final[max(0, enox_pos - 10) : enox_pos + 50]
            print(f"Leaflet final excerpt: '{leaflet_excerpt_clean}'")

    # Direct substring match on cleaned text
    if context_final in leaflet_final:
        if "enoxaparina" in context_normalized:
            print(f"✅ FOUND: Direct match after cleaning")
        return True

    # Handle various truncation patterns
    truncation_patterns = ["...", "..", "…"]

    for pattern in truncation_patterns:
        if context_final.endswith(pattern):
            partial_context = context_final[: -len(pattern)].strip()
            if len(partial_context) > 10 and partial_context in leaflet_final:
                if "enoxaparina" in context_normalized:
                    print(f"✅ FOUND: Truncation match after cleaning")
                return True

    # Handle mid-word truncation
    words = context_final.split()
    if len(words) > 2:
        # Try without the last word (which might be truncated)
        partial_without_last_word = " ".join(words[:-1])
        if (
            len(partial_without_last_word) > 15
            and partial_without_last_word in leaflet_final
        ):
            if "enoxaparina" in context_normalized:
                print(f"✅ FOUND: Match without last word after cleaning")
            return True

        # Try first 70% of text
        cutoff = int(len(context_final) * 0.7)
        if cutoff > 15:
            partial_70_percent = context_final[:cutoff].strip()
            if partial_70_percent in leaflet_final:
                if "enoxaparina" in context_normalized:
                    print(f"✅ FOUND: 70% match after cleaning")
                return True

    if "enoxaparina" in context_normalized:
        print(f"❌ NOT FOUND: No match for enoxaparina text even after cleaning")

    return False


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

        # print(messages)

        response = client.responses.parse(
            model=model,
            input=messages,
            temperature=temperature,
            text_format=Contraindications,
        )
        print("ehyooooooo")
        return response.output_parsed
    except Exception as e:
        print(f"❌ Error calling OpenAI API: {e}")
        return None


def build_prompt(prompt_template: str, leaflet_section: str) -> str:
    """Build the complete prompt using template and leaflet section."""
    return prompt_template.format(leaflet_contraindications=leaflet_section)


def process_single_leaflet(
    filename: str,
    leaflet_sections_dir: str,
    user_prompt_template: str,
    system_prompt: str,
    model: str,
    temperature: float,
):
    """
    Process a single leaflet file and extract contraindications.

    Returns:
        True if successful, False otherwise.
    """
    leaflet_file_path = os.path.join(leaflet_sections_dir, filename)

    print(f"🔍 Processing leaflet section: {filename}")

    # Metadata extraction
    aic = extract_aic_from_filename(filename)
    url = generate_url_from_aic(aic)

    # Read leaflet section
    with open(leaflet_file_path, "r", encoding="utf-8") as file:
        leaflet_section = file.read()

    # Build and send prompt
    user_prompt = build_prompt(user_prompt_template, leaflet_section)
    response = call_llm(
        prompt=user_prompt[:100],
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
    )

    print(response)
    pdb.set_trace()

    return response


def extract_all_contraindications(
    system_prompt_path: str = "data/prompts/system_prompt.txt",
    user_prompt_path: str = "data/prompts/user_prompt_template.txt",
    leaflet_sections_dir: str = "data/leaflets/sections",
    output_file: str = "data/contraindications/all_contraindications.json",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> None:
    """Extract contraindications from all leaflets and save to a single JSON file."""

    #
    all_contraindications = []

    # Read prompts
    with open(user_prompt_path, "r", encoding="utf-8") as file:
        user_prompt_template = file.read()
    with open(system_prompt_path, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    # Create output directory
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Process files
    import random

    md_files = [f for f in os.listdir(leaflet_sections_dir) if f.endswith(".md")]
    random.shuffle(md_files)
    total_processed = len(md_files)

    for filename in md_files:
        response = process_single_leaflet(
            filename,
            leaflet_sections_dir,
            user_prompt_template,
            system_prompt,  # Pass system prompt
            model,
            temperature,
        )

    all_contraindications.append(response)

    # Save all contraindications to single file
    print(f"\n💾 Saving all contraindications to: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_contraindications, f, indent=2, ensure_ascii=False)

    # Print summary
    total_contraindications = sum(
        len(entry["contraindications"]) for entry in all_contraindications
    )
    print(f"\n📊 EXTRACTION SUMMARY:")
    print(f"=" * 50)
    print(f"Total files processed: {len(md_files)}")
    print(f"Total contraindications: {total_contraindications}")
    print(f"Output file: {output_file}")


def extract_aic_from_filename(filename: str) -> str:
    """Extract AIC code from filename. Adjust this based on your filename format."""
    return filename.split("_")[-1].split(".")[0]


def generate_url_from_aic(aic: str) -> str:
    """Generate the PDF URL from AIC code."""
    if not aic:
        return ""
    # You'll need to adjust this based on how your URLs are structured
    # This is a placeholder - you might need to extract more info from the filename
    return f"https://farmaci.agenziafarmaco.gov.it/aifa/servlet/PdfDownloadServlet?pdfFileName=FI_XXXXX_{aic}.pdf&sys=m"


def translate_to_english(italian_text: str) -> str:
    """
    Translate Italian text to English.
    For now, returns a placeholder. You could integrate with a translation service.
    """
    # Placeholder - you could integrate with Google Translate API or similar
    return f"English translation of: {italian_text[:50]}..."


# Update your main section
if __name__ == "__main__":
    import sys

    extract_all_contraindications(
        system_prompt_path="data/prompts/system_prompt.txt",
        user_prompt_path="data/prompts/user_prompt_template.txt",
        leaflet_sections_dir="data/leaflets/sections",
        output_file="data/contraindications/all_contraindications.json",
    )

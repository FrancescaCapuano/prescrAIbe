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

    name: str
    source: str
    context: str


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
            contraindications_list = [c.model_dump() for c in response.contraindication]
        elif hasattr(response, "model_dump"):
            # response is a single Contraindication object
            contraindications_list = [response.model_dump()]
        elif isinstance(response, list):
            # response is already a list of objects
            contraindications_list = [
                c.model_dump() if hasattr(c, "model_dump") else c for c in response
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
    system_prompt_path: str = "data/prompts/system_prompt.txt",
    user_prompt_path: str = "data/prompts/user_prompt_template.txt",
    leaflet_sections_dir: str = "data/leaflet/sections",
    output_dir: str = "data/extracted_contraindications",
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


def test_extraction_with_verification(
    system_prompt_path: str = "data/prompts/system_prompt.txt",
    user_prompt_path: str = "data/prompts/user_prompt_template.txt",
    leaflet_sections_dir: str = "data/leaflets/sections",
    output_dir: str = "data/extracted_contraindications/test",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    test_count: int = 5,  # Only test first 5 files
) -> None:
    """
    Test extraction on a small subset and verify extracted content is in leaflets.
    """
    import random

    # Setup
    os.makedirs(output_dir, exist_ok=True)

    # Read prompts
    with open(user_prompt_path, "r", encoding="utf-8") as file:
        user_prompt_template = file.read()

    with open(system_prompt_path, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    # Get ALL files and randomly sample from them
    all_md_files = [f for f in os.listdir(leaflet_sections_dir) if f.endswith(".md")]

    # Set seed for reproducible results (optional - remove for true randomness)
    random.seed(42)  # Remove this line for different random samples each time

    # Randomly select test_count files
    md_files = random.sample(all_md_files, min(test_count, len(all_md_files)))

    print(f"🧪 TESTING EXTRACTION ON {len(md_files)} RANDOMLY SELECTED FILES")
    print(f"📁 Total available files: {len(all_md_files)}")
    print(f"🎲 Selected files: {[f for f in md_files]}")
    print("=" * 60)

    test_results = []

    for i, filename in enumerate(md_files, 1):
        print(f"\n📄 Test {i}/{len(md_files)}: {filename}")
        print("-" * 40)

        # Read leaflet section
        leaflet_file_path = os.path.join(leaflet_sections_dir, filename)
        with open(leaflet_file_path, "r", encoding="utf-8") as file:
            leaflet_section = file.read()

        print(f"📊 Leaflet section length: {len(leaflet_section)} characters")
        print(f"📝 Preview: {leaflet_section[:200]}...")

        # Extract contraindications
        user_prompt = build_prompt(user_prompt_template, leaflet_section)
        response = call_llm(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
        )

        if response is None:
            print(f"❌ Failed to get response for {filename}")
            test_results.append(
                {
                    "filename": filename,
                    "status": "API_FAILED",
                    "contraindications": [],
                    "verification": [],
                }
            )
            continue

        # Process response
        if hasattr(response, "contraindication") and isinstance(
            response.contraindication, list
        ):
            contraindications_list = [c.model_dump() for c in response.contraindication]
        elif hasattr(response, "model_dump"):
            contraindications_list = [response.model_dump()]
        elif isinstance(response, list):
            contraindications_list = [
                c.model_dump() if hasattr(c, "model_dump") else c for c in response
            ]
        else:
            contraindications_list = [response]

        print(f"🔍 Extracted {len(contraindications_list)} contraindications:")

        # Verify each contraindication
        verification_results = []
        for j, contraindication in enumerate(contraindications_list, 1):
            if isinstance(contraindication, dict):
                # Extract just the source text for verification
                contraindication_text = contraindication.get("source", "")
                display_name = contraindication.get("name", "Unknown")
            else:
                contraindication_text = str(contraindication)
                display_name = contraindication_text[:50] + "..."

            # Check if this contraindication SOURCE is actually in the leaflet
            is_present = context_is_in_leaflet(contraindication_text, leaflet_section)

            verification_results.append(
                {
                    "contraindication_name": display_name,
                    "contraindication_source": contraindication_text,
                    "present_in_leaflet": is_present,
                }
            )

            status_icon = "✅" if is_present else "❌"
            print(f"  {j}. {status_icon} {display_name}")
            if not is_present:
                print(
                    f"     Source: {contraindication_text[:100]}{'...' if len(contraindication_text) > 100 else ''}"
                )

        # Calculate verification stats
        total_contraindications = len(verification_results)
        verified_contraindications = sum(
            1 for v in verification_results if v["present_in_leaflet"]
        )
        verification_rate = (
            (verified_contraindications / total_contraindications * 100)
            if total_contraindications > 0
            else 0
        )

        print(
            f"📊 Verification: {verified_contraindications}/{total_contraindications} ({verification_rate:.1f}%) present in leaflet"
        )

        test_results.append(
            {
                "filename": filename,
                "status": "SUCCESS",
                "contraindications": contraindications_list,
                "verification": verification_results,
                "verification_rate": verification_rate,
            }
        )

        # Save individual test result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_json = f"{output_dir}/test_{filename.replace('.md', '')}_{timestamp}.json"

        test_data = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "temperature": temperature,
                "source_file": filename,
                "leaflet_section_length": len(leaflet_section),
                "total_contraindications": total_contraindications,
                "verified_contraindications": verified_contraindications,
                "verification_rate": verification_rate,
            },
            "leaflet_section_preview": (
                leaflet_section[:500] + "..."
                if len(leaflet_section) > 500
                else leaflet_section
            ),
            "extracted_contraindications": contraindications_list,
            "verification_results": verification_results,
        }

        with open(test_json, "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)

    # Print overall test summary
    print(f"\n🧪 TEST SUMMARY")
    print("=" * 60)

    successful_tests = [r for r in test_results if r["status"] == "SUCCESS"]
    failed_tests = [r for r in test_results if r["status"] != "SUCCESS"]

    if successful_tests:
        total_contraindications = sum(
            len(r["contraindications"]) for r in successful_tests
        )
        total_verified = sum(
            sum(1 for v in r["verification"] if v["present_in_leaflet"])
            for r in successful_tests
        )
        overall_verification_rate = (
            (total_verified / total_contraindications * 100)
            if total_contraindications > 0
            else 0
        )

        print(f"📊 Overall Results:")
        print(f"  • Successful extractions: {len(successful_tests)}/{len(md_files)}")
        print(f"  • Total contraindications extracted: {total_contraindications}")
        print(f"  • Contraindications verified in leaflets: {total_verified}")
        print(f"  • Overall verification rate: {overall_verification_rate:.1f}%")

        print(f"\n📋 Per-file verification rates:")
        for result in successful_tests:
            print(f"  • {result['filename']}: {result['verification_rate']:.1f}%")

    if failed_tests:
        print(f"\n❌ Failed extractions: {len(failed_tests)}")
        for result in failed_tests:
            print(f"  • {result['filename']}: {result['status']}")

    print(f"\n💾 Test results saved to: {output_dir}")

    # Return summary for programmatic use
    return {
        "total_files": len(md_files),
        "successful_extractions": len(successful_tests),
        "failed_extractions": len(failed_tests),
        "overall_verification_rate": (
            overall_verification_rate if successful_tests else 0
        ),
        "test_results": test_results,
    }


# Add this to your main section
if __name__ == "__main__":
    # Test on small subset first
    print("🧪 Running test extraction with verification...")

    test_results = test_extraction_with_verification(
        system_prompt_path="data/prompts/system_prompt.txt",
        user_prompt_path="data/prompts/user_prompt_template.txt",
        leaflet_sections_dir="data/leaflets/sections",
        output_dir="data/extracted_contraindications/test",
        test_count=10,  # Test only 5 files
    )

    print(
        f"\n🎯 Test completed! Overall verification rate: {test_results['overall_verification_rate']:.1f}%"
    )

    # Ask user if they want to proceed with full extraction
    if test_results["overall_verification_rate"] > 70:  # If >70% verified
        proceed = input("\n✅ Test looks good! Proceed with full extraction? (y/n): ")
        if proceed.lower() == "y":
            print("\n🚀 Running full extraction...")
            extract_contraindications()
    else:
        print(
            "\n⚠️  Low verification rate - you may want to adjust prompts before full extraction."
        )

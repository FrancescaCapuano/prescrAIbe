import json
import os
from pydoc import text
import re
from datetime import datetime
from pathlib import Path
from tqdm import tqdm


def context_is_in_leaflet(context, leaflet, debug=False):
    """
    Check if a given context is present in the leaflet text.
    Uses flexible matching to handle truncation and formatting differences.
    """
    context_lower = context.lower().strip()
    leaflet_lower = leaflet.lower()

    # Remove bullet point characters if present at the beginning of the context
    if context_lower.startswith("- "):
        context_lower = context_lower[2:].strip()

    # Remove "se ha" from beginning of context
    if context_lower.startswith("se ha"):
        context_lower = context_lower[5:].strip()

    # Remove quotes and normalize
    context_clean = context_lower.replace("'", "").replace('"', "")

    # CRITICAL: Normalize whitespace and newlines PROPERLY
    context_normalized = re.sub(r"\s+", " ", context_clean).strip()
    leaflet_normalized = re.sub(r"\s+", " ", leaflet_lower).strip()
    leaflet_normalized = leaflet_normalized.replace("\n", " ").replace("\r", " ")
    leaflet_normalized = re.sub(
        r"(\r\n|[\n\r\u2028\u2029\u0085\x0b\x0c\x1c-\x1f])", " ", leaflet_normalized
    )

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

    # 1. Direct substring match
    if context_final in leaflet_final:
        if debug:
            print(f"✅ FOUND: Direct match")
        return True

    # 2. Handle truncation patterns
    truncation_patterns = ["...", "..", "…"]
    for pattern in truncation_patterns:
        if context_final.endswith(pattern):
            partial_context = context_final[: -len(pattern)].strip()
            if len(partial_context) > 10 and partial_context in leaflet_final:
                if debug:
                    print(f"✅ FOUND: Truncation match")
                return True

    # 3. Handle mid-word truncation
    words = context_final.split()
    if len(words) > 2:
        # Try without the last word (in case it's cut off)
        partial_without_last_word = " ".join(words[:-1])
        if (
            len(partial_without_last_word) > 15
            and partial_without_last_word in leaflet_final
        ):
            if debug:
                print(f"✅ FOUND: Match without last word")
            return True

        # Try first 70% of text
        cutoff = int(len(context_final) * 0.7)
        if cutoff > 15:
            partial_70_percent = context_final[:cutoff].strip()
            if partial_70_percent in leaflet_final:
                if debug:
                    print(f"✅ FOUND: 70% match")
                return True

    if debug:
        print(f"❌ NOT FOUND: No match found")
        print(f"Context: {context_final[:100]}...")

    return False


def find_leaflet_file(aic: str, leaflet_sections_dir: str):
    """Find the corresponding leaflet file for an AIC code."""
    # Look for files ending with the AIC code
    for filename in os.listdir(leaflet_sections_dir):
        if filename.endswith(f"{aic}.md"):
            return os.path.join(leaflet_sections_dir, filename)
    return None


def verify_contraindications(
    contraindications_file: str = "data/contraindications/all_contraindications.json",
    leaflet_sections_dir: str = "data/leaflets/sections",
    output_file: str = "data/contraindications/all_contraindications_verified.json",
    unverified_report_file: str = "data/contraindications/unverified_report.json",
):
    """Verify all contraindications against their original leaflets."""

    print("🔍 Starting context verification process...")

    # Load the contraindications data
    if not os.path.exists(contraindications_file):
        print(f"❌ Contraindications file not found: {contraindications_file}")
        return

    with open(contraindications_file, "r", encoding="utf-8") as f:
        all_contraindications = json.load(f)

    print(f"📋 Loaded {len(all_contraindications)} entries to verify")

    # Verification statistics
    total_contraindications = 0
    verified_contraindications = 0
    unverified_contraindications = 0
    entries_processed = 0
    entries_with_missing_leaflets = 0
    unverified_details = []

    # Process each entry with progress bar
    with tqdm(all_contraindications, desc="Verifying entries", unit="entry") as pbar:
        for entry_idx, entry in enumerate(pbar):
            aic = entry.get("aic", "")
            entry_contraindications = entry.get("contraindications", [])

            pbar.set_description(f"Verifying AIC {aic}")

            # Find the corresponding leaflet file
            leaflet_file_path = find_leaflet_file(aic, leaflet_sections_dir)

            if not leaflet_file_path:
                entries_with_missing_leaflets += 1
                pbar.set_postfix({"⚠️": f"Missing leaflet for {aic}"})
                tqdm.write(f"⚠️  No leaflet found for AIC: {aic}")

                # Mark all contraindications as unverified
                for contraindication in entry_contraindications:
                    contraindication["context_verified"] = False
                    contraindication["verification_timestamp"] = (
                        datetime.now().isoformat()
                    )
                    contraindication["verification_error"] = "Leaflet file not found"

                    unverified_details.append(
                        {
                            "aic": aic,
                            "contraindication_id": contraindication["id"],
                            "context": (contraindication["context"]),
                            "reason": "Leaflet file not found",
                        }
                    )

                total_contraindications += len(entry_contraindications)
                unverified_contraindications += len(entry_contraindications)
                continue

            # Read the leaflet content
            try:
                with open(leaflet_file_path, "r", encoding="utf-8") as f:
                    leaflet_content = f.read()
            except Exception as e:
                tqdm.write(f"❌ Error reading leaflet {leaflet_file_path}: {e}")
                continue

            # Verify each contraindication in this entry
            entry_verified = 0
            entry_unverified = 0

            for contraindication in entry_contraindications:
                context = contraindication.get("context", "")
                total_contraindications += 1

                # Perform verification
                is_verified = context_is_in_leaflet(context, leaflet_content)

                # Add verification fields
                contraindication["context_verified"] = is_verified
                contraindication["verification_timestamp"] = datetime.now().isoformat()

                if is_verified:
                    verified_contraindications += 1
                    entry_verified += 1
                else:
                    unverified_contraindications += 1
                    entry_unverified += 1

                    # Add to unverified details
                    unverified_details.append(
                        {
                            "aic": aic,
                            "contraindication_id": contraindication["id"],
                            "context": (contraindication["context"]),
                            "reason": "Context not found in leaflet",
                        }
                    )

            # Update entry-level verification stats
            entry["verification_stats"] = {
                "verified": entry_verified,
                "unverified": entry_unverified,
                "total": len(entry_contraindications),
                "verification_rate": (
                    entry_verified / len(entry_contraindications)
                    if entry_contraindications
                    else 0
                ),
            }

            entries_processed += 1

            # Update progress bar with verification stats
            verification_rate = (
                (verified_contraindications / total_contraindications * 100)
                if total_contraindications > 0
                else 0
            )
            pbar.set_postfix(
                {
                    "✅": f"{entry_verified}v",
                    "❌": f"{entry_unverified}u",
                    "📊": f"{verification_rate:.1f}%",
                }
            )

            # Print per-entry results
            if entry_contraindications:
                entry_rate = entry_verified / len(entry_contraindications) * 100
                tqdm.write(
                    f"📄 AIC {aic}: {entry_verified}/{len(entry_contraindications)} verified ({entry_rate:.1f}%)"
                )

    # Calculate final statistics
    overall_verification_rate = (
        (verified_contraindications / total_contraindications * 100)
        if total_contraindications > 0
        else 0
    )

    # Save verified data
    print(f"\n💾 Saving verified data to: {output_file}")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_contraindications, f, indent=2, ensure_ascii=False)

    # Save unverified report
    print(f"💾 Saving unverified report to: {unverified_report_file}")
    unverified_report = {
        "summary": {
            "total_contraindications": total_contraindications,
            "verified_contraindications": verified_contraindications,
            "unverified_contraindications": unverified_contraindications,
            "verification_rate": overall_verification_rate,
            "entries_processed": entries_processed,
            "entries_with_missing_leaflets": entries_with_missing_leaflets,
            "verification_timestamp": datetime.now().isoformat(),
        },
        "unverified_contraindications": unverified_details,
    }

    with open(unverified_report_file, "w", encoding="utf-8") as f:
        json.dump(unverified_report, f, indent=2, ensure_ascii=False)

    # Print comprehensive final summary
    print(f"\n" + "=" * 80)
    print(f"🎯 VERIFICATION COMPLETE")
    print(f"=" * 80)

    print(f"\n📊 VERIFICATION STATISTICS:")
    print(f"Total entries processed: {entries_processed}")
    print(f"Entries with missing leaflets: {entries_with_missing_leaflets}")
    print(f"Total contraindications: {total_contraindications}")
    print(f"Verified contraindications: {verified_contraindications}")
    print(f"Unverified contraindications: {unverified_contraindications}")

    print(f"\n🏆 OVERALL VERIFICATION RATE: {overall_verification_rate:.1f}%")
    print(
        f"   ({verified_contraindications}/{total_contraindications} contraindications verified)"
    )

    print(f"\n💾 OUTPUT FILES:")
    print(f"Verified data: {output_file}")
    print(f"Unverified report: {unverified_report_file}")

    if entries_with_missing_leaflets > 0:
        print(f"\n⚠️  {entries_with_missing_leaflets} entries had missing leaflet files")

    # Show top unverified reasons
    if unverified_details:
        print(f"\n🔍 SAMPLE UNVERIFIED CONTRAINDICATIONS:")
        for i, detail in enumerate(unverified_details[:5], 1):
            print(f"{i}. AIC {detail['aic']}: {detail['context']}")
            print(f"   Reason: {detail['reason']}")

    print(f"\n" + "=" * 80)


def verify_single_entry(
    aic: str,
    contraindications_file: str = "data/contraindications/all_contraindications.json",
    leaflet_sections_dir: str = "data/leaflets/sections",
):
    """Verify a single entry for debugging purposes."""

    # Load data
    with open(contraindications_file, "r", encoding="utf-8") as f:
        all_contraindications = json.load(f)

    # Find the entry
    target_entry = None
    for entry in all_contraindications:
        if entry.get("aic") == aic:
            target_entry = entry
            break

    if not target_entry:
        print(f"❌ No entry found for AIC: {aic}")
        return

    # Find leaflet
    leaflet_file_path = find_leaflet_file(aic, leaflet_sections_dir)
    if not leaflet_file_path:
        print(f"❌ No leaflet found for AIC: {aic}")
        return

    # Read leaflet
    with open(leaflet_file_path, "r", encoding="utf-8") as f:
        leaflet_content = f.read()

    print(
        f"🔍 Verifying AIC {aic} with {len(target_entry['contraindications'])} contraindications"
    )
    print(f"📄 Leaflet file: {leaflet_file_path}")

    # Verify each contraindication with debug output
    for i, contraindication in enumerate(target_entry["contraindications"], 1):
        context = contraindication.get("context", "")
        print(f"\n📋 Contraindication {i}:")
        print(f"Context: {context[:100]}...")

        is_verified = context_is_in_leaflet(context, leaflet_content, debug=True)
        print(f"Result: {'✅ VERIFIED' if is_verified else '❌ NOT VERIFIED'}")

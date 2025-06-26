import re
import os
from pathlib import Path
from typing import List, Tuple


def extract_numbered_sections(
    md_text: str, debug: bool = False
) -> List[Tuple[int, str, str]]:
    """
    Extracts all numbered sections from the cleaned markdown text.
    Returns a list of (section_number, title, section_content).
    """
    # Step 1: Normalize strikethrough and bold
    clean_text = re.sub(r"~~\*\*(.+?)\*\*~~", r"\1", md_text)
    clean_text = re.sub(r"\*\*(.+?)\*\*", r"\1", clean_text)

    # Step 2: Find all headers and their positions
    pattern = re.compile(r"^\s*(\d+)\s*[\.\-]?\s+(.+)$", re.MULTILINE)
    headers = []

    # Define patterns to filter out fake headers
    fake_header_patterns = [
        r"documento.*reso.*disponibile.*da.*aifa",
    ]

    for match in pattern.finditer(clean_text):
        section = int(match.group(1))
        title = match.group(2).strip()

        # Check if this is a fake header
        is_fake = False
        title_lower = title.lower()

        for fake_pattern in fake_header_patterns:
            if re.search(fake_pattern, title_lower):
                is_fake = True
                if debug:
                    print(f"🚫 Skipping fake header: {section}. {title}")
                break

        # Only add real headers
        if not is_fake:
            start_idx = match.start()
            headers.append((section, title, start_idx))
            if debug:
                print(f"✅ Found real header: {section}. {title}")

    # Step 3: Extract section content between headers
    results = []
    for idx, (section, title, start_idx) in enumerate(headers):
        end_idx = headers[idx + 1][2] if idx + 1 < len(headers) else None
        section_content = clean_text[start_idx:end_idx].strip()
        results.append((section, title, section_content))

    return results


def get_sections_by_number(md_text: str, section_num: int, debug: bool = False) -> list:
    """
    Returns a list of unique section contents for the given section number, preserving order.
    Skips sections where the content is just the header.
    """
    sections = extract_numbered_sections(md_text, debug=debug)
    seen = set()
    unique_sections = []
    for sec, title, content in sections:
        header_str = f"{sec}. {title}"
        if (
            sec == section_num
            and content not in seen
            and content.strip().lower() != header_str
        ):
            unique_sections.append(content)
            seen.add(content)
    return unique_sections


def extract_section_from_leaflets(
    input_dir: str, output_dir: str, section_num: int = 1
):
    """
    Extracts a specific section from all markdown files in the input directory
    and saves them to the output directory.
    """

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    i = 0
    files_processed = 0

    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            files_processed += 1
            print(f"\n📄 Processing: {filename}")

            with open(os.path.join(input_dir, filename), "r", encoding="utf-8") as f:
                md_text = f.read()

            # Show all numbered sections found in this file
            all_sections = extract_numbered_sections(md_text, debug=False)
            if all_sections:
                print(f"📋 Found {len(all_sections)} numbered sections:")
                for sec, title, content in all_sections:
                    print(f"   {sec}. {title}")
            else:
                print(f"❌ No numbered sections found!")

            # Extract the requested section
            sections = get_sections_by_number(md_text, section_num)
            if sections:
                output_filename = os.path.join(output_dir, filename)
                with open(output_filename, "w", encoding="utf-8") as out_f:
                    out_f.write("\n\n".join(sections))
                print(f"✅ Extracted section {section_num}")
            else:
                print(f"❌ No section {section_num} found - saving whole document")
                i += 1

                output_filename = os.path.join(output_dir, filename)
                with open(output_filename, "w", encoding="utf-8") as out_f:
                    out_f.write(md_text)

    print(f"\n📊 SUMMARY:")
    print(f"Files processed: {files_processed}")
    print(f"Files with section {section_num}: {files_processed - i}")
    print(f"Files without section {section_num}: {i}")


if __name__ == "__main__":
    extract_section_from_leaflets(
        "data/leaflets/processed", "data/leaflets/sections", section_num=2
    )

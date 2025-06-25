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

    # DEBUG: Only print if debug=True
    if debug:
        lines = clean_text.split("\n")
        for i, line in enumerate(lines[:20]):  # First 20 lines
            if "2." in line or "Cosa" in line:
                print(f"DEBUG Line {i}: '{line}'")

    # Step 2: Find all headers and their positions - Updated pattern
    pattern = re.compile(r"^\s*(\d+)\s*[\.\-]?\s+(.+)$", re.MULTILINE)
    headers = []
    for match in pattern.finditer(clean_text):
        section = int(match.group(1))
        title = match.group(2).strip().lower()
        start_idx = match.start()
        headers.append((section, title, start_idx))
        if debug:
            print(f"DEBUG Found header: {section}. {title}")  # Debug print

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
    deleted_files = []

    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            with open(os.path.join(input_dir, filename), "r", encoding="utf-8") as f:
                md_text = f.read()

            sections = get_sections_by_number(md_text, section_num)
            if sections:
                output_filename = os.path.join(output_dir, filename)
                with open(output_filename, "w", encoding="utf-8") as out_f:
                    out_f.write("\n\n".join(sections))
                # print(f"Extracted section {section_num} from {filename} to {output_filename}")
            else:
                print(f"No section {section_num} found in {filename}")
                i += 1
                file_path = os.path.join(input_dir, filename)

                output_filename = os.path.join(output_dir, filename)
                with open(output_filename, "w", encoding="utf-8") as out_f:
                    out_f.write(md_text)

    print(f"Total files with no section {section_num}: {i}")


if __name__ == "__main__":
    extract_section_from_leaflets(
        "data/leaflets/processed", "data/leaflets/sections", section_num=2
    )

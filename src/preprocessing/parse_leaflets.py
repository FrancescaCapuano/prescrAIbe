import pymupdf4llm
import pathlib
import os
import glob
import re
from typing import List, Tuple
from collections import defaultdict


def extract_numbered_sections(md_text: str) -> List[Tuple[int, str, str]]:
    """
    Extracts all numbered sections from the cleaned markdown text.
    Returns a list of (section_number, title, section_content).
    """
    # Step 1: Normalize strikethrough and bold
    clean_text = re.sub(r"~~\*\*(.+?)\*\*~~", r"\1", md_text)
    clean_text = re.sub(r"\*\*(.+?)\*\*", r"\1", clean_text)

    # Step 2: Find all headers and their positions
    pattern = re.compile(
        r"^\s*(\d+)\s*[\.\-]?\s+([A-Z][A-Z\s]{3,})$", re.MULTILINE | re.IGNORECASE
    )
    headers = []
    for match in pattern.finditer(clean_text):
        section = int(match.group(1))
        title = match.group(2).strip().lower()
        start_idx = match.start()
        headers.append((section, title, start_idx))

    # Step 3: Extract section content between headers
    results = []
    for idx, (section, title, start_idx) in enumerate(headers):
        end_idx = headers[idx + 1][2] if idx + 1 < len(headers) else None
        section_content = clean_text[start_idx:end_idx].strip()
        results.append((section, title, section_content))

    return results


def get_sections_by_number(md_text: str, section_num: int) -> list:
    """
    Returns a list of unique section contents for the given section number, preserving order.
    Skips sections where the content is just the header.
    """
    sections = extract_numbered_sections(md_text)
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


def convert_pdf_to_markdown(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def process_pdf(pdf_path: str, output_md_path: str) -> str:
    """
    Converts a PDF to markdown using pymupdf4llm, extracts all sections by number,
    and writes them all to a single markdown file.
    """
    md_text = convert_pdf_to_markdown(pdf_path)
    md_sections = get_sections_by_number(md_text, section_num=2)

    for section in md_sections:
        print(section[:500])
        print("-" * 80)
    # Join all sections with two newlines as separator
    md_combined = "\n\n".join(md_sections)
    pathlib.Path(output_md_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(output_md_path).write_bytes(md_combined.encode("utf-8"))
    print(f"Markdown written to {output_md_path}")
    return md_combined


def process_pdfs(pdfs: list, output_dir: str) -> None:
    """
    Processes all PDF files in the input directory and saves their markdown versions in the output directory.
    """
    for pdf in pdfs:
        file_name = os.path.basename(pdf)
        output_path = os.path.join(output_dir, file_name.replace(".pdf", ".md"))
        process_pdf(pdf, output_path)


# Example usage:
if __name__ == "__main__":

    # Recursively find all FI_*.pdf files in ../data/leaflets/raw
    fi_files = glob.glob("data/leaflets/raw/FI_*_035313.pdf")[:2]
    print(fi_files)

    print(f"Found {len(fi_files)} FI_ files.")

    process_pdfs(fi_files, "data/leaflets/processed")

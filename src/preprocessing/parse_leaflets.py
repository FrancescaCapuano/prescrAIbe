import re


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

import re
import os
from pathlib import Path
from typing import List, Tuple


def fix_broken_italian_words(text):
    """Fix common Italian words broken by AIFA watermarks"""
    import re

    # Medical terms that commonly get broken
    word_repairs = {
        r"coagulazi\s+one": "coagulazione",
        r"com\s+porta": "comporta",
        r"sanguina\s+mento": "sanguinamento",
        r"somministra\s+zione": "somministrazione",
        r"vaccina\s+zione": "vaccinazione",
        r"gravi\s+danza": "gravidanza",
        r"allatta\s+mento": "allattamento",
        r"precau\s+zioni": "precauzioni",
        r"protezio\s+ne": "protezione",
        r"infezio\s+ne": "infezione",
        r"immuno\s+deficienza": "immunodeficienza",
        r"malat\s+tia": "malattia",
        r"compo\s+nenti": "componenti",
        r"allergi\s+ca": "allergica",
        r"allergi\s+co": "allergico",
        r"sistema\s+immunitario": "sistema immunitario",
        r"febbre\s+alta": "febbre alta",
        r"difetto\s+genetico": "difetto genetico",
        r"principi\s+attivi": "principi attivi",
        r"reazio\s+ne": "reazione",
        r"disturbo\s+della": "disturbo della",
        # Generic patterns for common Italian endings
        r"(\w{3,})\s+(zione)\b": r"\1\2",  # *-zione words
        r"(\w{3,})\s+(mento)\b": r"\1\2",  # *-mento words
        r"(\w{3,})\s+(tura)\b": r"\1\2",  # *-tura words
        r"(\w{3,})\s+(tore)\b": r"\1\2",  # *-tore words
    }

    for pattern, replacement in word_repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def extract_numbered_sections(md_text: str) -> List[Tuple[int, str, str]]:
    """
    Extracts all numbered sections from the cleaned markdown text.
    Returns a list of (section_number, title, section_content).
    """
    # Step 1: Remove AIFA metadata completely FIRST
    clean_text = re.sub(
        r"~~Documento~~ ~~reso~~ ~~disponibile~~ ~~da~~ ~~AIFA~~.*?~~",
        "",
        md_text,
        flags=re.DOTALL,
    )

    # CRITICAL: Remove AIFA watermarks that split text
    clean_text = re.sub(
        r"Esula dalla competenza dell'AIFA.*?all'immissione in commercio \(o titolare AIC\)\.",
        "",
        clean_text,
        flags=re.DOTALL,
    )

    # Remove page numbers and dates that appear with watermarks
    clean_text = re.sub(r"^\s*\d+\s*$", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"il \d{2}/\d{2}/\d{4}~~", "", clean_text)
    clean_text = re.sub(r"~~.*?~~", "", clean_text, flags=re.DOTALL)

    # Clean strikethrough in different formats
    clean_text = re.sub(r"~~\*\*(.+?)\*\*~~", r"\1", clean_text)  # ~~**text**~~
    clean_text = re.sub(r"~~(.+?)~~", r"\1", clean_text)  # ~~text~~
    clean_text = re.sub(r"\*\*(.+?)\*\*", r"\1", clean_text)  # **text**

    # Fix spaced letters caused by partial strikethrough
    clean_text = re.sub(
        r"\bs\s*a\s*p\s*e\s*r\s*e\b", "sapere", clean_text, flags=re.IGNORECASE
    )
    clean_text = re.sub(r"\bd\s*e\s*v\s*e\b", "deve", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\bc\s*o\s*s\s*a\b", "cosa", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(
        r"\bp\s*r\s*i\s*m\s*a\b", "prima", clean_text, flags=re.IGNORECASE
    )
    clean_text = re.sub(
        r"\bu\s*s\s*a\s*r\s*e\b", "usare", clean_text, flags=re.IGNORECASE
    )
    clean_text = re.sub(r"\bc\s*o\s*m\s*e\b", "come", clean_text, flags=re.IGNORECASE)

    # Fix extra spaces and clean up formatting
    clean_text = re.sub(r"(\d+)\s*\.\s+", r"\1. ", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text)  # Normalize all whitespace
    clean_text = re.sub(r"\n\s*\n", "\n", clean_text)  # Remove empty lines

    # CRITICAL: Fix broken Italian words AFTER removing watermarks
    clean_text = fix_broken_italian_words(clean_text)

    # Step 2: Define section patterns - ONLY match actual
    valid_section_patterns = [
        (1, r"^\s*1\s*\.\s+(Cos[aè].*e a cosa serve|What.*is.*and what.*is.*used for)"),
        (
            2,
            r"^\s*2\s*\.\s+(?:Cosa\s+deve\s+sapere\s+prima|Che cosa deve sapere|Prima\s+di|What.*you\s+need\s+to\s+know\s+before|Before.*you.*take)",
        ),
        (
            3,
            r"^\s*3\s*\.\s+(Come.*(?:usare|prendere|viene.*somministrato|dato)|How\s+to.*(?:take|use))",
        ),
        (4, r"^\s*4\s*\.\s+(Possibili effetti|Possible side effects|Side effects)"),
        (5, r"^\s*5\s*\.\s+(Come conservare|How to store)"),
        (
            6,
            r"^\s*6\s*\.\s+(Contenuto.*confezione|Contents.*of.*pack|Package contents)",
        ),
    ]

    # Add patterns for section headers without numbers
    unnumbered_section_patterns = [
        (2, r"^\s*CONTROINDICAZIONI\s*$"),
        (2, r"^\s*Controindicazioni\s*$"),
    ]

    headers = []

    # Find numbered sections
    for section_num, pattern in valid_section_patterns:
        matches = re.finditer(pattern, clean_text, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            full_match = match.group(0)
            title = full_match.split(".", 1)[1].strip()
            start_idx = match.start()
            headers.append((section_num, title, start_idx))

    # Find unnumbered sections (only if numbered version not found)
    found_sections = {header[0] for header in headers}

    for section_num, pattern in unnumbered_section_patterns:
        if section_num not in found_sections:
            matches = re.finditer(pattern, clean_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                title = match.group(0).strip()
                start_idx = match.start()
                headers.append((section_num, title, start_idx))

    # Sort headers by their position in the document
    headers.sort(key=lambda x: x[2])

    # Extract section content between headers
    results = []
    for idx, (section, title, start_idx) in enumerate(headers):
        end_idx = headers[idx + 1][2] if idx + 1 < len(headers) else None
        section_content = clean_text[start_idx:end_idx].strip()

        # Remove the header line from content
        lines = section_content.split("\n")
        if lines and (
            re.match(r"^\s*\d+\s*\.", lines[0])
            or lines[0].strip().upper() in ["CONTROINDICAZIONI"]
        ):
            section_content = "\n".join(lines[1:]).strip()

        # Only add if there's actual content
        if section_content:
            results.append((section, title, section_content))

    return results


def get_sections_by_number(md_text: str, section_num: int) -> list:
    """
    Returns a list of unique section contents for the given section number.
    """
    sections = extract_numbered_sections(md_text)
    seen = set()
    unique_sections = []

    for sec, title, content in sections:
        if sec == section_num and content not in seen:
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
    files_without_section = 0
    files_processed = 0

    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            files_processed += 1

            with open(os.path.join(input_dir, filename), "r", encoding="utf-8") as f:
                md_text = f.read()

            sections = get_sections_by_number(md_text, section_num)
            output_filename = os.path.join(output_dir, filename)

            if sections:
                final_content = "\n\n".join(sections)
                with open(output_filename, "w", encoding="utf-8") as out_f:
                    out_f.write(final_content)
            else:
                files_without_section += 1

    print(f"📊 SUMMARY:")
    print(f"Files processed: {files_processed}")
    print(
        f"Files with section {section_num}: {files_processed - files_without_section}"
    )
    print(f"Files without section {section_num}: {files_without_section}")

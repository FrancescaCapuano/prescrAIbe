import os
import pathlib
import requests
from dotenv import load_dotenv
import time

load_dotenv()

DEEPL_API_KEY = os.getenv(
    "DEEPL_API_KEY"
)  # Set your DeepL API key as an environment variable


def translate_text(text: str, source_lang: str = "IT", target_lang: str = "DE") -> str:
    """
    Translates text from source_lang to target_lang using DeepL API.
    """
    if not DEEPL_API_KEY:
        print("DeepL API key not found. Set DEEPL_API_KEY environment variable.")
        return text
    url = "https://api-free.deepl.com/v2/translate"
    params = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "tag_handling": "xml",  # helps preserve **bold** if needed
    }
    try:
        response = requests.post(url, data=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["translations"][0]["text"]
    except Exception as e:
        print(f"Translation failed: {e}")
        return text


def translate_markdown_file(input_md_path: str, output_md_path: str) -> None:
    """
    Translates a markdown file from Italian to German and saves the result.
    Splits the file into paragraphs to avoid API length limits.
    """
    with open(input_md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    # Split by double newlines (paragraphs)
    paragraphs = md_text.split("\n\n")
    translated_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if para:
            translated = translate_text(para, source_lang="IT", target_lang="DE")
            print("ORIGINAL:", para)
            print("TRANSLATED:", translated)
            print("-" * 40)
            translated_paragraphs.append(translated)
            time.sleep(2)  # Add a 2-second delay between requests
        else:
            translated_paragraphs.append("")
    translated_md = "\n\n".join(translated_paragraphs)
    pathlib.Path(output_md_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(translated_md)
    print(f"Translated markdown written to {output_md_path}")


if __name__ == "__main__":
    # Example usage: translate a specific file
    input_md_path = (
        "data/interim/CITALOPRAM/RCP_003602_036327.md"  # Change this path as needed
    )
    output_md_path = (
        "data/interim/CITALOPRAM/translated/RCP_003602_036327_de.md"  # Change as needed
    )
    translate_markdown_file(input_md_path, output_md_path)

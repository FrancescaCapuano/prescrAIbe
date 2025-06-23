import requests
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class ICD11Extractor:
    def __init__(self, code_filter=None, chapter_filter=None, digit_lengths=None):
        """
        Initialize the ICD-11 extractor

        Args:
            code_filter (str or list or None): Filter for which codes to extract
                - None: Extract ALL codes (full database)
                - "1": Extract only codes starting with "1" (e.g., 1A00, 1C44)
                - ["1", "2"]: Extract codes starting with "1" or "2"
                - "1A": Extract codes starting with "1A"
                - ["1A", "1B"]: Extract codes starting with "1A" or "1B"

            chapter_filter (str or list or None): Filter by chapter name/number
                - None: All chapters
                - 1 or "1": Chapter 1 (Certain infectious or parasitic diseases)
                - [1, 2]: Chapters 1 and 2
                - "infectious": Chapters containing "infectious" in the title
                - ["infectious", "neoplasms"]: Multiple chapter keywords

            digit_lengths (list or None): Filter by code length (number of digits)
                - None: ALL digit lengths (2, 3, 4, 5+ digits)
                - [4]: Only 4-digit codes (e.g., 1A00, 2B34)
                - [3, 4]: Both 3-digit and 4-digit codes
                - [2, 3, 4, 5]: Multiple digit lengths
        """
        self.client_id = os.getenv("ICD_CLIENT_ID")
        self.client_secret = os.getenv("ICD_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "ICD_CLIENT_ID and ICD_CLIENT_SECRET must be set in .env file"
            )

        # Set up filtering
        self.code_filter = self._setup_code_filter(code_filter)
        self.chapter_filter = self._setup_chapter_filter(chapter_filter)
        self.digit_lengths = digit_lengths  # None means all lengths

        # ICD-11 Chapter mapping (approximate - will be refined when we get actual data)
        self.chapter_info = {
            1: {"keywords": ["infectious", "parasitic"], "code_range": "1"},
            2: {"keywords": ["neoplasms"], "code_range": "2"},
            3: {"keywords": ["blood", "immune"], "code_range": "3"},
            4: {
                "keywords": ["endocrine", "nutritional", "metabolic"],
                "code_range": "5",
            },
            5: {
                "keywords": ["mental", "behavioural", "neurodevelopmental"],
                "code_range": "6",
            },
            6: {"keywords": ["sleep-wake"], "code_range": "7"},
            7: {"keywords": ["nervous"], "code_range": "8"},
            8: {"keywords": ["eye", "adnexa"], "code_range": "9"},
            9: {"keywords": ["ear", "mastoid"], "code_range": "AB"},
            10: {"keywords": ["circulatory"], "code_range": "B"},
            11: {"keywords": ["respiratory"], "code_range": "C"},
            12: {"keywords": ["digestive"], "code_range": "D"},
            13: {"keywords": ["skin"], "code_range": "E"},
            14: {"keywords": ["musculoskeletal", "connective"], "code_range": "F"},
            15: {"keywords": ["genitourinary"], "code_range": "G"},
            16: {
                "keywords": ["pregnancy", "childbirth", "puerperium"],
                "code_range": "J",
            },
            17: {"keywords": ["perinatal"], "code_range": "K"},
            18: {"keywords": ["developmental", "anomalies"], "code_range": "L"},
            19: {"keywords": ["symptoms", "signs", "findings"], "code_range": "M"},
            20: {"keywords": ["injury", "poisoning", "external"], "code_range": "N"},
            21: {"keywords": ["external", "morbidity", "mortality"], "code_range": "P"},
            22: {"keywords": ["factors", "health", "contact"], "code_range": "Q"},
            23: {"keywords": ["extension"], "code_range": "X"},
        }

        self.token = None
        self.headers = None
        self.output_dir = Path(__file__).parent.parent.parent / "data" / "ICD-codes"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.authenticate()

    def _setup_code_filter(self, code_filter):
        """Setup the code filter for easy checking"""
        if code_filter is None:
            return None
        elif isinstance(code_filter, str):
            return [code_filter.upper()]
        elif isinstance(code_filter, list):
            return [f.upper() for f in code_filter]
        else:
            raise ValueError("code_filter must be None, string, or list of strings")

    def _setup_chapter_filter(self, chapter_filter):
        """Setup the chapter filter"""
        if chapter_filter is None:
            return None
        elif isinstance(chapter_filter, (int, str)):
            return [str(chapter_filter).lower()]
        elif isinstance(chapter_filter, list):
            return [str(f).lower() for f in chapter_filter]
        else:
            raise ValueError("chapter_filter must be None, int, string, or list")

    def _should_include_chapter(self, chapter_title, chapter_uri):
        """Check if a chapter should be included based on the filter"""
        if self.chapter_filter is None:
            return True

        chapter_title_lower = chapter_title.lower() if chapter_title else ""

        for filter_item in self.chapter_filter:
            # Check if it's a chapter number
            if filter_item.isdigit():
                chapter_num = int(filter_item)
                if chapter_num in self.chapter_info:
                    # Check if any keyword matches
                    for keyword in self.chapter_info[chapter_num]["keywords"]:
                        if keyword in chapter_title_lower:
                            return True
            else:
                # Check if the filter item is in the chapter title
                if filter_item in chapter_title_lower:
                    return True

        return False

    def _should_include_code(self, code):
        """Check if a code should be included based on the filter"""
        if self.code_filter is None:
            return True  # Include all codes

        if not code:
            return False

        code_upper = code.upper().replace(".", "").replace("-", "")

        for filter_prefix in self.code_filter:
            if code_upper.startswith(filter_prefix):
                return True

        return False

    def _should_include_code_length(self, code):
        """Check if a code should be included based on digit length filter"""
        if self.digit_lengths is None:
            return True  # Include all digit lengths

        if not code:
            return False

        code_clean = code.replace(".", "").replace("-", "").replace(" ", "")
        code_length = len(code_clean)

        return code_length in self.digit_lengths

    def authenticate(self):
        """Get OAuth2 token"""
        token_endpoint = "https://icdaccessmanagement.who.int/connect/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "icdapi_access",
            "grant_type": "client_credentials",
        }

        response = requests.post(token_endpoint, data=payload)
        if response.status_code == 200:
            self.token = response.json()["access_token"]

            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Accept-Language": "en",
                "API-Version": "v2",
            }
            print("Authentication successful!")
        else:
            raise Exception(
                f"Authentication failed: {response.status_code} - {response.text}"
            )

    def extract_all_codes(self, release_id="2025-01"):
        """Extract all codes with complete information (renamed from extract_all_4_digit_codes)"""

        filter_desc = (
            "ALL codes"
            if self.code_filter is None
            else f"codes starting with: {', '.join(self.code_filter)}"
        )
        chapter_desc = (
            "ALL chapters"
            if self.chapter_filter is None
            else f"chapters: {', '.join(self.chapter_filter)}"
        )
        length_desc = (
            "ALL digit lengths"
            if self.digit_lengths is None
            else f"digit lengths: {', '.join(map(str, self.digit_lengths))}"
        )

        print(f"Extracting {filter_desc} from {chapter_desc} with {length_desc}")

        # Start from MMS root
        root_url = f"https://id.who.int/icd/release/11/{release_id}/mms"
        response = requests.get(root_url, headers=self.headers)

        if response.status_code != 200:
            print(f"Error accessing root: {response.status_code}")
            return []

        root_data = response.json()

        all_codes = []
        chapters_to_process = []

        # First, get chapter information and filter
        print("\nAvailable chapters:")
        for i, chapter_uri in enumerate(root_data.get("child", []), 1):
            # Get chapter info
            chapter_response = requests.get(
                chapter_uri.replace("http://", "https://"), headers=self.headers
            )
            if chapter_response.status_code == 200:
                chapter_data = chapter_response.json()
                chapter_title = (
                    chapter_data.get("title", {}).get("@value", "")
                    if isinstance(chapter_data.get("title"), dict)
                    else str(chapter_data.get("title", ""))
                )

                print(f"  Chapter {i}: {chapter_title}")

                if self._should_include_chapter(chapter_title, chapter_uri):
                    chapters_to_process.append((i, chapter_uri, chapter_title))
                    print(f"    -> SELECTED for processing")
                else:
                    print(f"    -> Skipped (doesn't match filter)")
            time.sleep(0.1)

        if not chapters_to_process:
            print("No chapters match your filter criteria!")
            return []

        print(f"\nProcessing {len(chapters_to_process)} selected chapters...")

        # Process selected chapters
        for i, (chapter_num, chapter_uri, chapter_title) in enumerate(
            chapters_to_process, 1
        ):
            print(
                f"\nProcessing chapter {i}/{len(chapters_to_process)}: {chapter_title}"
            )
            chapter_codes = self.extract_from_branch(chapter_uri)
            all_codes.extend(chapter_codes)
            print(f"Found {len(chapter_codes)} matching codes in this chapter")
            time.sleep(0.1)  # Be respectful to the API

        return all_codes

    def extract_from_branch(self, uri):
        """Recursively extract 4-digit codes from a branch"""
        codes = []

        api_url = uri.replace("http://", "https://")

        # Add include parameter to get more comprehensive data
        if "?" in api_url:
            api_url += "&include=ancestor,descendant"
        else:
            api_url += "?include=ancestor,descendant"

        response = requests.get(api_url, headers=self.headers)

        if response.status_code != 200:
            print(f"Error fetching {uri}: {response.status_code}")
            return codes

        entity_data = response.json()

        # Check if this is a category that matches ALL our filters
        if (
            entity_data.get("classKind") == "category"
            and entity_data.get("code")
            and self._should_include_code(entity_data.get("code"))
            and self._should_include_code_length(entity_data.get("code"))
        ):

            # Extract complete information
            code_info = self.extract_complete_info(entity_data)
            codes.append(code_info)
            code_length = len(
                entity_data.get("code", "").replace(".", "").replace("-", "")
            )
            print(f"  Found matching {code_length}-digit code: {code_info['code']}")

        # Process children
        for child_uri in entity_data.get("child", []):
            child_codes = self.extract_from_branch(child_uri)
            codes.extend(child_codes)
            time.sleep(0.05)  # API rate limiting

        return codes

    def extract_complete_info(self, entity_data):
        """Extract ALL available information from the API (excluding postcoordination)"""

        def safe_extract_value(data, default=""):
            """Safely extract value from API response, handling different formats"""
            if data is None:
                return default
            elif isinstance(data, dict):
                return data.get("@value", default)
            elif isinstance(data, str):
                return data
            else:
                return str(data) if data else default

        def safe_extract_list(data_list):
            """Safely extract list of items with labels and references"""
            if not data_list:
                return []

            processed = []
            for item in data_list:
                if isinstance(item, dict):
                    processed_item = {
                        "label": safe_extract_value(item.get("label", "")),
                        "foundation_reference": item.get("foundationReference", ""),
                        "linearization_reference": item.get(
                            "linearizationReference", ""
                        ),
                        "id": item.get("@id", ""),
                        "code_range": item.get("codeRange", ""),
                        "sort_weight": item.get("sortWeight", ""),
                        "lang": item.get("lang", ""),
                    }
                    # Remove empty values
                    processed_item = {k: v for k, v in processed_item.items() if v}
                    processed.append(processed_item)
                else:
                    processed.append({"label": str(item)})

            return processed

        # Extract all available information
        complete_info = {
            # Basic identification
            "@context": entity_data.get("@context", ""),
            "@id": entity_data.get("@id", ""),
            "@type": entity_data.get("@type", ""),
            # Core properties
            "code": entity_data.get("code", ""),
            "title": safe_extract_value(entity_data.get("title")),
            "definition": safe_extract_value(entity_data.get("definition")),
            "long_definition": safe_extract_value(entity_data.get("longDefinition")),
            "fully_specified_name": safe_extract_value(
                entity_data.get("fullySpecifiedName")
            ),
            # Classification properties
            "class_kind": entity_data.get("classKind", ""),
            "block_id": entity_data.get("blockId", ""),
            "code_range": entity_data.get("codeRange", ""),
            "sort_weight": entity_data.get("sortWeight", ""),
            # Hierarchical relationships
            "parent": entity_data.get("parent", []),
            "child": entity_data.get("child", []),
            "ancestor": entity_data.get("ancestor", []),
            "descendant": entity_data.get("descendant", []),
            # Terms and synonyms
            "synonym": safe_extract_list(entity_data.get("synonym", [])),
            "narrower_term": safe_extract_list(entity_data.get("narrowerTerm", [])),
            "inclusion": safe_extract_list(entity_data.get("inclusion", [])),
            "exclusion": safe_extract_list(entity_data.get("exclusion", [])),
            "index_term": safe_extract_list(entity_data.get("indexTerm", [])),
            # Cross-references
            "coded_elsewhere": safe_extract_list(entity_data.get("codedElsewhere", [])),
            "coded_note": safe_extract_list(entity_data.get("codingNote", [])),
            "see_also": safe_extract_list(entity_data.get("seeAlso", [])),
            # Foundation-specific
            "foundation_child_elsewhere": entity_data.get(
                "foundationChildElsewhere", []
            ),
            "foundation_reference": entity_data.get("foundationReference", ""),
            "linearization_reference": entity_data.get("linearizationReference", ""),
            "source": entity_data.get("source", ""),
            # Browser and versioning
            "browser_url": entity_data.get("browserUrl", ""),
            "release_id": entity_data.get("releaseId", ""),
            "release_date": entity_data.get("releaseDate", ""),
            # Language and localization
            "lang": entity_data.get("lang", ""),
            # Additional classification info
            "is_residual": entity_data.get("isResidual", ""),
            "rubric_kind": entity_data.get("rubricKind", ""),
            # Status and flags
            "is_leaf": entity_data.get("isLeaf", ""),
            "chapter": entity_data.get("chapter", ""),
            # Usage and application
            "use_additional_code": safe_extract_list(
                entity_data.get("useAdditionalCode", [])
            ),
            "code_first": safe_extract_list(entity_data.get("codeFirst", [])),
            "code_also": safe_extract_list(entity_data.get("codeAlso", [])),
            # Diagnostic criteria (for mental health disorders)
            "diagnostic_criteria": safe_extract_value(
                entity_data.get("diagnosticCriteria")
            ),
            # ICD-O morphology (for neoplasms)
            "icdo_morphology": safe_extract_value(entity_data.get("icdoMorphology")),
            # Additional notes and comments
            "note": safe_extract_value(entity_data.get("note")),
            "coding_hint": safe_extract_value(entity_data.get("codingHint")),
            # Statistical and epidemiological
            "statistical_note": safe_extract_value(entity_data.get("statisticalNote")),
            # Other properties that might be present
            "manifestation_properties": entity_data.get("manifestationProperties", {}),
            "scale_info": entity_data.get("scaleInfo", {}),
            "value_id": entity_data.get("valueId", ""),
            # Extension code related (non-postcoordination)
            "required_postcoordination": entity_data.get(
                "requiredPostcoordination", []
            ),
            "allowed_postcoordination": entity_data.get("allowedPostcoordination", []),
            "default_postcoordination": entity_data.get("defaultPostcoordination", []),
        }

        # Remove empty fields to keep the JSON clean
        cleaned_info = {}
        for key, value in complete_info.items():
            if value:  # Keep non-empty values
                if isinstance(value, list) and len(value) == 0:
                    continue  # Skip empty lists
                elif isinstance(value, dict) and len(value) == 0:
                    continue  # Skip empty dictionaries
                elif isinstance(value, str) and value.strip() == "":
                    continue  # Skip empty strings
                else:
                    cleaned_info[key] = value

        return cleaned_info

    def process_exclusions(self, exclusions):
        """Process exclusion information"""
        processed = []
        for exclusion in exclusions:
            if isinstance(exclusion, dict):
                label = exclusion.get("label", {})
                if isinstance(label, dict):
                    label_text = label.get("@value", "")
                else:
                    label_text = str(label)

                processed.append(
                    {
                        "label": label_text,
                        "foundation_reference": exclusion.get("foundationReference"),
                        "linearization_reference": exclusion.get(
                            "linearizationReference"
                        ),
                    }
                )
            else:
                processed.append({"label": str(exclusion)})
        return processed

    def process_inclusions(self, inclusions):
        """Process inclusion terms"""
        processed = []
        for inclusion in inclusions:
            if isinstance(inclusion, dict):
                label = inclusion.get("label", {})
                if isinstance(label, dict):
                    label_text = label.get("@value", "")
                else:
                    label_text = str(label)

                processed.append(
                    {
                        "label": label_text,
                        "foundation_reference": inclusion.get("foundationReference"),
                    }
                )
            else:
                processed.append({"label": str(inclusion)})
        return processed

    def process_narrower_terms(self, narrower_terms):
        """Process narrower terms"""
        processed = []
        for term in narrower_terms:
            if isinstance(term, dict):
                label = term.get("label", {})
                if isinstance(label, dict):
                    label_text = label.get("@value", "")
                else:
                    label_text = str(label)

                processed.append(
                    {
                        "label": label_text,
                        "foundation_reference": term.get("foundationReference"),
                    }
                )
            else:
                processed.append({"label": str(term)})
        return processed

    def process_coded_elsewhere(self, coded_elsewhere):
        """Process coded elsewhere references"""
        processed = []
        for item in coded_elsewhere:
            if isinstance(item, dict):
                label = item.get("label", {})
                if isinstance(label, dict):
                    label_text = label.get("@value", "")
                else:
                    label_text = str(label)

                processed.append(
                    {
                        "label": label_text,
                        "foundation_reference": item.get("foundationReference"),
                        "linearization_reference": item.get("linearizationReference"),
                    }
                )
            else:
                processed.append({"label": str(item)})
        return processed


# Usage
if __name__ == "__main__":
    # ========================== CONFIGURATION ==========================
    # Change these settings to control what codes to extract:

    # === CODE FILTERING ===
    # Option 1: Extract ALL codes (full database) - WARNING: This will take a very long time!
    code_filter = None

    # Option 2: Extract only codes starting with specific prefixes
    # code_filter = "1"               # Codes starting with 1 (e.g., 1A00, 1C44, 1F25)
    # code_filter = "1A0"  # Codes starting with 1A0 (e.g., 1A00, 1A01, 1A02)
    # code_filter = ["1A", "1B"]      # Codes starting with 1A or 1B

    # === CHAPTER FILTERING ===
    # Option 1: Extract from ALL chapters
    # chapter_filter = None

    # Option 2: Extract from specific chapters by number
    chapter_filter = 1  # Chapter 1: Certain infectious or parasitic diseases
    # chapter_filter = [1, 2]         # Chapters 1 and 2

    # Option 3: Extract from chapters by keyword in title
    # chapter_filter = "infectious"   # Chapters with "infectious" in the title
    # chapter_filter = ["infectious", "neoplasms"]  # Multiple keywords

    # === DIGIT LENGTH FILTERING ===
    # Option 1: Extract ALL digit lengths (2, 3, 4, 5+ digits)
    digit_lengths = None  # Include all: 1A (2), 1A0 (3), 1A00 (4), 1A001 (5), etc.

    # Option 2: Extract specific digit lengths
    # digit_lengths = [4]             # Only 4-digit codes (e.g., 1A00, 1B23)
    # digit_lengths = [3, 4]          # Both 3-digit and 4-digit codes

    # ===================================================================

    try:
        extractor = ICD11Extractor(
            code_filter=code_filter,
            chapter_filter=chapter_filter,
            digit_lengths=digit_lengths,
        )
        print("Starting ICD-11 extraction...")

        all_codes = extractor.extract_all_codes()

        # Create filename based on filters
        filename_parts = []
        if code_filter is None:
            filename_parts.append("all_codes")
        elif isinstance(code_filter, str):
            filename_parts.append(f"codes_{code_filter.lower()}")
        else:
            filename_parts.append(f"codes_{'_'.join([f.lower() for f in code_filter])}")

        if chapter_filter is not None:
            if isinstance(chapter_filter, (int, str)):
                filename_parts.append(f"chapter_{str(chapter_filter).lower()}")
            else:
                filename_parts.append(
                    f"chapters_{'_'.join([str(f).lower() for f in chapter_filter])}"
                )

        if digit_lengths is not None:
            filename_parts.append(f"digits_{'_'.join(map(str, digit_lengths))}")
        else:
            filename_parts.append("all_digits")

        filename = f"icd11_{'_'.join(filename_parts)}.json"

        # Save to file in the same directory as this script
        output_file = extractor.output_dir / filename
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_codes, f, indent=2, ensure_ascii=False)

        print(f"\nExtraction complete! Found {len(all_codes)} codes.")
        print(f"Data saved to: {output_file}")

        # Print some example codes found
        if all_codes:
            print("\nSample codes extracted:")
            for i, code in enumerate(all_codes[:10]):
                code_length = len(code["code"].replace(".", "").replace("-", ""))
                print(f"  {code['code']} ({code_length}-digit): {code['title']}")
            if len(all_codes) > 10:
                print(f"  ... and {len(all_codes) - 10} more")

            # Show breakdown by digit length
            length_breakdown = {}
            for code in all_codes:
                length = len(code["code"].replace(".", "").replace("-", ""))
                length_breakdown[length] = length_breakdown.get(length, 0) + 1

            print(f"\nBreakdown by digit length:")
            for length in sorted(length_breakdown.keys()):
                print(f"  {length}-digit codes: {length_breakdown[length]}")

    except ValueError as e:
        print(f"Error: {e}")
        print(
            "Please make sure your .env file exists in the project root with ICD_CLIENT_ID and ICD_CLIENT_SECRET"
        )
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()


# define function get_icd_description to extract the description of a given ICD code *********************************************************


def get_icd_description(icd_code, json_file_dir="./"):
    """
    Extract the definition/description for a given ICD-11 code.

    Args:
        icd_code (str): The ICD-11 code to search for (e.g., "1A00")

    Returns:
        str: The definition/description of the ICD code, or None if not found
    """
    # Path to the JSON file relative to the script location
    json_file_path = os.path.join(
        json_file_dir,
        "icd11_all_codes_chapter_1_all_digits.json",
    )

    try:
        # Load the JSON data
        with open(json_file_path, "r", encoding="utf-8") as file:
            icd_data = json.load(file)
        print(icd_data[0])

        # Search for the matching code
        for entry in icd_data:
            if entry.get("code") == icd_code:
                print(f"Found entry for code: {icd_code}")
                # Return the definition if it exists, otherwise return the title
                definition = entry.get("definition")
                if definition:
                    return definition
                else:
                    # Some entries might not have a definition, so return title as fallback
                    return entry.get("title", "No description available")

        # If code not found
        return None

    except FileNotFoundError:
        print(f"Error: Could not find the JSON file at {json_file_path}")
        return None
    except json.JSONDecodeError:
        print("Error: Could not parse the JSON file")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

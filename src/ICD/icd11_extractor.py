import requests
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv


# load ICD database to local json

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
        # Updated chapter_info dictionary based on official ICD-11 structure
        # Source: https://icdcdn.who.int/icd11referenceguide/en/html/index.html

        self.chapter_info = {
            1: {
                "title": "Certain infectious or parasitic diseases",
                "keywords": [
                    "infectious",
                    "parasitic",
                    "bacteria",
                    "virus",
                    "infection",
                    "antimicrobial",
                ],
                "code_range": "1",  # Codes starting with 1 (e.g., 1A00-1G9Z)
                "new_in_icd11": False,
                "description": "Includes diseases generally recognized as communicable or transmissible, antimicrobial resistance codes",
            },
            2: {
                "title": "Neoplasms",
                "keywords": [
                    "neoplasm",
                    "cancer",
                    "tumor",
                    "tumour",
                    "malignant",
                    "benign",
                    "carcinoma",
                ],
                "code_range": "2",  # Codes starting with 2 (e.g., 2A00-2F9Z)
                "new_in_icd11": False,
                "description": "All neoplasms, whether functionally active or not",
            },
            3: {
                "title": "Diseases of the blood or blood-forming organs",
                "keywords": [
                    "blood",
                    "hematologic",
                    "haematologic",
                    "anemia",
                    "anaemia",
                    "bleeding",
                ],
                "code_range": "3",  # Codes starting with 3 (e.g., 3A00-3C9Z)
                "new_in_icd11": False,
                "description": "Diseases of blood and blood-forming organs and certain immune mechanism disorders",
            },
            4: {
                "title": "Diseases of the immune system",
                "keywords": [
                    "immune",
                    "immunodeficiency",
                    "allergy",
                    "hypersensitivity",
                    "autoimmune",
                ],
                "code_range": "4",  # Codes starting with 4 (e.g., 4A00-4B9Z)
                "new_in_icd11": True,
                "description": "NEW CHAPTER: Primary immunodeficiencies, allergic and hypersensitivity conditions",
            },
            5: {
                "title": "Endocrine, nutritional or metabolic diseases",
                "keywords": [
                    "endocrine",
                    "hormone",
                    "diabetes",
                    "thyroid",
                    "metabolic",
                    "nutrition",
                ],
                "code_range": "5",  # Codes starting with 5 (e.g., 5A00-5D9Z)
                "new_in_icd11": False,
                "description": "Disorders of internal secretion and metabolism",
            },
            6: {
                "title": "Mental, behavioural or neurodevelopmental disorders",
                "keywords": [
                    "mental",
                    "psychiatric",
                    "behavioral",
                    "behavioural",
                    "neurodevelopmental",
                    "autism",
                ],
                "code_range": "6",  # Codes starting with 6 (e.g., 6A00-6E9Z)
                "new_in_icd11": False,
                "description": "Mental, behavioural and neurodevelopmental disorders",
            },
            7: {
                "title": "Sleep-wake disorders",
                "keywords": [
                    "sleep",
                    "wake",
                    "insomnia",
                    "hypersomnia",
                    "circadian",
                    "sleep disorders",
                ],
                "code_range": "7",  # Codes starting with 7 (e.g., 7A00-7B9Z)
                "new_in_icd11": True,
                "description": "NEW CHAPTER: Sleep-wake disorders, previously scattered across different chapters",
            },
            8: {
                "title": "Diseases of the nervous system",
                "keywords": [
                    "nervous",
                    "neurological",
                    "brain",
                    "spinal",
                    "nerve",
                    "stroke",
                    "dementia",
                ],
                "code_range": "8",  # Codes starting with 8 (e.g., 8A00-8E9Z)
                "new_in_icd11": False,
                "description": "Diseases of the nervous system, now includes cerebrovascular diseases",
            },
            9: {
                "title": "Diseases of the visual system",
                "keywords": [
                    "eye",
                    "visual",
                    "vision",
                    "ophthalmic",
                    "retina",
                    "glaucoma",
                ],
                "code_range": "9",  # Codes starting with 9 (e.g., 9A00-9D9Z)
                "new_in_icd11": False,
                "description": "Diseases of the eye and adnexa",
            },
            10: {
                "title": "Diseases of the ear or mastoid process",
                "keywords": [
                    "ear",
                    "hearing",
                    "mastoid",
                    "auditory",
                    "deafness",
                    "otitis",
                ],
                "code_range": "A",  # Codes starting with A (e.g., AA00-AB9Z)
                "new_in_icd11": False,
                "description": "Diseases of the ear and mastoid process",
            },
            11: {
                "title": "Diseases of the circulatory system",
                "keywords": [
                    "circulatory",
                    "cardiovascular",
                    "heart",
                    "blood pressure",
                    "hypertension",
                ],
                "code_range": "B",  # Codes starting with B (e.g., BA00-BE9Z)
                "new_in_icd11": False,
                "description": "Diseases of the circulatory system, excludes cerebrovascular diseases (moved to Chapter 8)",
            },
            12: {
                "title": "Diseases of the respiratory system",
                "keywords": [
                    "respiratory",
                    "lung",
                    "breathing",
                    "pneumonia",
                    "asthma",
                    "pulmonary",
                ],
                "code_range": "C",  # Codes starting with C (e.g., CA00-CB9Z)
                "new_in_icd11": False,
                "description": "Diseases of the respiratory system",
            },
            13: {
                "title": "Diseases of the digestive system",
                "keywords": [
                    "digestive",
                    "gastrointestinal",
                    "stomach",
                    "intestine",
                    "liver",
                    "gastro",
                ],
                "code_range": "D",  # Codes starting with D (e.g., DA00-DE9Z)
                "new_in_icd11": False,
                "description": "Diseases of the digestive system",
            },
            14: {
                "title": "Diseases of the skin",
                "keywords": ["skin", "dermatological", "dermatitis", "eczema", "rash"],
                "code_range": "E",  # Codes starting with E (e.g., EA00-EB9Z)
                "new_in_icd11": False,
                "description": "Diseases of the skin and subcutaneous tissue",
            },
            15: {
                "title": "Diseases of the musculoskeletal system or connective tissue",
                "keywords": [
                    "musculoskeletal",
                    "bone",
                    "joint",
                    "muscle",
                    "arthritis",
                    "connective",
                ],
                "code_range": "F",  # Codes starting with F (e.g., FA00-FC9Z)
                "new_in_icd11": False,
                "description": "Diseases of the musculoskeletal system and connective tissue",
            },
            16: {
                "title": "Diseases of the genitourinary system",
                "keywords": [
                    "genitourinary",
                    "kidney",
                    "urinary",
                    "genital",
                    "renal",
                    "bladder",
                ],
                "code_range": "G",  # Codes starting with G (e.g., GA00-GC9Z)
                "new_in_icd11": False,
                "description": "Diseases of the genitourinary system",
            },
            17: {
                "title": "Conditions related to sexual health",
                "keywords": [
                    "sexual",
                    "gender",
                    "reproductive",
                    "contraception",
                    "sexuality",
                ],
                "code_range": "H",  # Codes starting with H (e.g., HA00-HA9Z)
                "new_in_icd11": True,
                "description": "NEW CHAPTER: Sexual health and gender identity conditions",
            },
            18: {
                "title": "Pregnancy, childbirth or the puerperium",
                "keywords": [
                    "pregnancy",
                    "childbirth",
                    "obstetric",
                    "maternal",
                    "puerperium",
                    "delivery",
                ],
                "code_range": "J",  # Codes starting with J (e.g., JA00-JB9Z)
                "new_in_icd11": False,
                "description": "Pregnancy, childbirth and the puerperium",
            },
            19: {
                "title": "Certain conditions originating in the perinatal period",
                "keywords": [
                    "perinatal",
                    "neonatal",
                    "newborn",
                    "birth",
                    "fetal",
                    "infant",
                ],
                "code_range": "K",  # Codes starting with K (e.g., KA00-KC9Z)
                "new_in_icd11": False,
                "description": "Certain conditions originating in the perinatal period",
            },
            20: {
                "title": "Developmental anomalies",
                "keywords": [
                    "developmental",
                    "congenital",
                    "anomalies",
                    "malformations",
                    "birth defects",
                ],
                "code_range": "L",  # Codes starting with L (e.g., LA00-LD9Z)
                "new_in_icd11": False,
                "description": "Developmental anomalies",
            },
            21: {
                "title": "Symptoms, signs or clinical findings, not elsewhere classified",
                "keywords": [
                    "symptoms",
                    "signs",
                    "findings",
                    "abnormal",
                    "unspecified",
                ],
                "code_range": "M",  # Codes starting with M (e.g., MA00-MG9Z)
                "new_in_icd11": False,
                "description": "Symptoms, signs or clinical findings, not elsewhere classified",
            },
            22: {
                "title": "Injury, poisoning or certain other consequences of external causes",
                "keywords": [
                    "injury",
                    "trauma",
                    "poisoning",
                    "burn",
                    "fracture",
                    "wound",
                ],
                "code_range": "N",  # Codes starting with N (e.g., NA00-NF9Z)
                "new_in_icd11": False,
                "description": "Injury, poisoning or certain other consequences of external causes",
            },
            23: {
                "title": "External causes of morbidity or mortality",
                "keywords": [
                    "external",
                    "accidents",
                    "violence",
                    "transport",
                    "falls",
                    "causes",
                ],
                "code_range": "P",  # Codes starting with P (e.g., PA00-PE9Z)
                "new_in_icd11": False,
                "description": "External causes of morbidity and mortality",
            },
            24: {
                "title": "Factors influencing health status or contact with health services",
                "keywords": [
                    "factors",
                    "health status",
                    "contact",
                    "screening",
                    "prevention",
                    "counseling",
                ],
                "code_range": "Q",  # Codes starting with Q (e.g., QA00-QF9Z)
                "new_in_icd11": False,
                "description": "Factors influencing health status and contact with health services",
            },
            25: {
                "title": "Codes for special purposes",
                "keywords": ["special", "provisional", "research", "experimental"],
                "code_range": "R",  # Codes starting with R (e.g., RA00-RZ9Z)
                "new_in_icd11": False,
                "description": "Codes for special purposes",
            },
            26: {
                "title": "Supplementary Chapter Traditional Medicine Conditions - Module 1",
                "keywords": [
                    "traditional",
                    "medicine",
                    "tcm",
                    "chinese",
                    "ayurveda",
                    "complementary",
                ],
                "code_range": "T",  # Codes starting with T (e.g., TM1-related codes)
                "new_in_icd11": True,
                "description": "NEW CHAPTER: Traditional Medicine conditions (supplementary)",
            },
            # Special sections and chapters
            "V": {
                "title": "Supplementary section for functioning assessment",
                "keywords": ["functioning", "disability", "capacity", "performance"],
                "code_range": "V",  # V-codes
                "new_in_icd11": True,
                "description": "NEW: Functioning assessment section",
            },
            "X": {
                "title": "Extension Codes",
                "keywords": [
                    "extension",
                    "postcoordination",
                    "severity",
                    "laterality",
                    "anatomical",
                ],
                "code_range": "X",  # X-codes (XA, XB, XC, etc.)
                "new_in_icd11": True,
                "description": "Extension codes for postcoordination (cannot be used alone)",
            },
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
                # For numeric filters, we need to determine the chapter number from the URI or position
                # Extract chapter number from URI or use a different approach
                # Since the URI structure might contain the chapter info, we can try to extract it

                # Alternative approach: extract chapter number from URI
                # ICD-11 URIs typically follow a pattern that can help identify the chapter
                chapter_num = int(filter_item)

                # Get the expected code range for this chapter
                if chapter_num in self.chapter_info:
                    expected_code_range = self.chapter_info[chapter_num]["code_range"]

                    # Check if the URI or title indicates this is the correct chapter
                    # We can also check against known chapter titles
                    expected_title_parts = self.chapter_info[chapter_num][
                        "title"
                    ].lower()

                    # Direct title matching (more reliable than keyword matching)
                    if expected_title_parts in chapter_title_lower:
                        return True

                    # If direct title matching fails, we could also check the URI structure
                    # or use the position in the chapters list (passed from calling function)

            else:
                # Check if the filter item is in the chapter title (for string-based filters)
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
        """Recursively extract codes from a branch"""
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

    def get_all_parent_info(self, entity_data):
        """Fetch all parent information up to the 01 level, excluding root-level entries"""
        all_parents = []

        def safe_extract_value(data, default=""):
            if data is None:
                return default
            elif isinstance(data, dict):
                return data.get("@value", default)
            elif isinstance(data, str):
                return data
            else:
                return str(data) if data else default

        def is_root_level_entry(parent_info):
            """Check if this is a root-level entry that should be excluded"""
            # Exclude entries that only have a title and no code
            if not parent_info.get("code") and parent_info.get("title"):
                title = parent_info.get("title", "").lower()
                # Check for common root-level titles
                if any(
                    phrase in title
                    for phrase in [
                        "icd-11 for mortality and morbidity statistics",
                        "mortality and morbidity statistics",
                        "icd-11",
                    ]
                ):
                    return True
            return False

        def should_stop_at_code(code):
            """Check if we should stop climbing at this code level"""
            if not code:
                return False

            # Stop at 01 level codes (like 01, 02, 03, etc.)
            clean_code = code.replace(".", "").replace("-", "").strip()

            # Check if it's a 2-digit code ending in 1 (01, 11, 21, etc.)
            if len(clean_code) == 2 and clean_code.endswith("1"):
                return True

            return False

        def get_parent_chain(current_entity_data, visited_uris=None):
            """Recursively get all parents up to the 01 level"""
            if visited_uris is None:
                visited_uris = set()

            parents = current_entity_data.get("parent", [])

            for parent_uri in parents:
                # Avoid infinite loops
                if parent_uri in visited_uris:
                    continue

                visited_uris.add(parent_uri)

                try:
                    api_url = parent_uri.replace("http://", "https://")
                    response = requests.get(api_url, headers=self.headers)

                    if response.status_code == 200:
                        parent_data = response.json()

                        parent_info = {
                            "code": parent_data.get("code", ""),
                            "title": safe_extract_value(parent_data.get("title")),
                            "definition": safe_extract_value(
                                parent_data.get("definition")
                            ),
                            "long_definition": safe_extract_value(
                                parent_data.get("longDefinition")
                            ),
                            "fully_specified_name": safe_extract_value(
                                parent_data.get("fullySpecifiedName")
                            ),
                        }

                        # Remove empty values
                        cleaned_parent_info = {
                            k: v for k, v in parent_info.items() if v
                        }

                        # Skip root-level entries
                        if is_root_level_entry(cleaned_parent_info):
                            continue

                        # Add this parent if it has meaningful content
                        if cleaned_parent_info:
                            all_parents.append(cleaned_parent_info)

                        # Check if we should stop climbing at this level
                        current_code = parent_data.get("code", "")
                        if should_stop_at_code(current_code):
                            continue  # Don't climb further, but we already added this parent

                        # Recursively get parents of this parent
                        get_parent_chain(parent_data, visited_uris)

                        time.sleep(0.05)  # Rate limiting

                    else:
                        print(
                            f"Error fetching parent info from {parent_uri}: {response.status_code}"
                        )

                except Exception as e:
                    print(f"Exception fetching parent info from {parent_uri}: {e}")

        # Start the recursive parent chain retrieval
        get_parent_chain(entity_data)

        return all_parents

    def extract_complete_info(self, entity_data):
        """Extract information based on code length requirements with consistent structure"""

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

        def collect_all_labels(entity_data):
            """Collect all labels from various fields into one list"""
            all_labels = []

            # Helper function to extract labels from different structures
            def extract_labels_from_field(field_data):
                labels = []
                if not field_data:
                    return labels

                if isinstance(field_data, list):
                    for item in field_data:
                        if isinstance(item, dict):
                            label = safe_extract_value(item.get("label", ""))
                            if label:
                                labels.append(label)
                        elif isinstance(item, str) and item:
                            labels.append(item)
                elif isinstance(field_data, dict):
                    label = safe_extract_value(field_data.get("label", ""))
                    if label:
                        labels.append(label)
                elif isinstance(field_data, str) and field_data:
                    labels.append(field_data)

                return labels

            # Collect labels from various fields
            fields_with_labels = [
                "synonym",
                "narrowerTerm",
                "inclusion",
                "exclusion",
                "indexTerm",
                "codedElsewhere",
                "codingNote",
                "seeAlso",
            ]

            for field in fields_with_labels:
                labels = extract_labels_from_field(entity_data.get(field, []))
                all_labels.extend(labels)

            # Remove duplicates while preserving order
            unique_labels = []
            seen = set()
            for label in all_labels:
                if label not in seen:
                    unique_labels.append(label)
                    seen.add(label)

            return unique_labels

        # Get code length to determine what information to include
        code = entity_data.get("code", "")
        code_length = len(code.replace(".", "").replace("-", "").replace(" ", ""))

        # For 4-5-6 digit codes, add specific information with specified order
        if code_length >= 4:
            # Get all parent information up to root level
            all_parent_info = self.get_all_parent_info(entity_data)

            # Add all labels in one list
            all_labels = collect_all_labels(entity_data)

            # Process inclusions specifically for 4-5-6 digit codes
            inclusions = entity_data.get("inclusion", [])
            inclusion_labels = []
            if inclusions:
                for inclusion in inclusions:
                    if isinstance(inclusion, dict):
                        label = safe_extract_value(inclusion.get("label", ""))
                        if label:
                            inclusion_labels.append(label)
                    elif isinstance(inclusion, str) and inclusion:
                        inclusion_labels.append(inclusion)

            # Build the ordered dictionary for 4-5-6 digit codes with consistent structure
            code_info = {
                "code": code if code else "",
                "title": (
                    safe_extract_value(entity_data.get("title"))
                    if entity_data.get("title")
                    else ""
                ),
                "fully_specified_name": (
                    safe_extract_value(entity_data.get("fullySpecifiedName"))
                    if entity_data.get("fullySpecifiedName")
                    else ""
                ),
                "definition": (
                    safe_extract_value(entity_data.get("definition"))
                    if entity_data.get("definition")
                    else ""
                ),
                "inclusions": inclusion_labels if inclusion_labels else [],
                "all_labels": all_labels if all_labels else [],
                "parent_info": all_parent_info if all_parent_info else [],
                "browser_url": (
                    entity_data.get("browserUrl", "")
                    if entity_data.get("browserUrl")
                    else ""
                ),
            }

        else:
            # For codes less than 4 digits, include all original information with consistent structure
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

            # Include all original fields for shorter codes with consistent structure
            complete_info = {
                # Basic identification
                "@context": entity_data.get("@context", ""),
                "@id": entity_data.get("@id", ""),
                "@type": entity_data.get("@type", ""),
                # Core properties
                "code": code if code else "",
                "title": (
                    safe_extract_value(entity_data.get("title"))
                    if entity_data.get("title")
                    else ""
                ),
                "definition": (
                    safe_extract_value(entity_data.get("definition"))
                    if entity_data.get("definition")
                    else ""
                ),
                "long_definition": (
                    safe_extract_value(entity_data.get("longDefinition"))
                    if entity_data.get("longDefinition")
                    else ""
                ),
                "fully_specified_name": (
                    safe_extract_value(entity_data.get("fullySpecifiedName"))
                    if entity_data.get("fullySpecifiedName")
                    else ""
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
                "coded_elsewhere": safe_extract_list(
                    entity_data.get("codedElsewhere", [])
                ),
                "coded_note": safe_extract_list(entity_data.get("codingNote", [])),
                "see_also": safe_extract_list(entity_data.get("seeAlso", [])),
                # Foundation-specific
                "foundation_child_elsewhere": entity_data.get(
                    "foundationChildElsewhere", []
                ),
                "foundation_reference": entity_data.get("foundationReference", ""),
                "linearization_reference": entity_data.get(
                    "linearizationReference", ""
                ),
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
                "diagnostic_criteria": (
                    safe_extract_value(entity_data.get("diagnosticCriteria"))
                    if entity_data.get("diagnosticCriteria")
                    else ""
                ),
                # ICD-O morphology (for neoplasms)
                "icdo_morphology": (
                    safe_extract_value(entity_data.get("icdoMorphology"))
                    if entity_data.get("icdoMorphology")
                    else ""
                ),
                # Additional notes and comments
                "note": (
                    safe_extract_value(entity_data.get("note"))
                    if entity_data.get("note")
                    else ""
                ),
                "coding_hint": (
                    safe_extract_value(entity_data.get("codingHint"))
                    if entity_data.get("codingHint")
                    else ""
                ),
                # Statistical and epidemiological
                "statistical_note": (
                    safe_extract_value(entity_data.get("statisticalNote"))
                    if entity_data.get("statisticalNote")
                    else ""
                ),
                # Other properties that might be present
                "manifestation_properties": entity_data.get(
                    "manifestationProperties", {}
                ),
                "scale_info": entity_data.get("scaleInfo", {}),
                "value_id": entity_data.get("valueId", ""),
                # Extension code related (non-postcoordination)
                "required_postcoordination": entity_data.get(
                    "requiredPostcoordination", []
                ),
                "allowed_postcoordination": entity_data.get(
                    "allowedPostcoordination", []
                ),
                "default_postcoordination": entity_data.get(
                    "defaultPostcoordination", []
                ),
            }

            # Keep all fields with consistent structure - convert empty strings to empty lists where appropriate
            code_info = {}
            for key, value in complete_info.items():
                # Always include the field, but ensure consistent structure
                if key in [
                    "parent",
                    "child",
                    "ancestor",
                    "descendant",
                    "synonym",
                    "narrower_term",
                    "inclusion",
                    "exclusion",
                    "index_term",
                    "coded_elsewhere",
                    "coded_note",
                    "see_also",
                    "foundation_child_elsewhere",
                    "use_additional_code",
                    "code_first",
                    "code_also",
                    "required_postcoordination",
                    "allowed_postcoordination",
                    "default_postcoordination",
                ]:
                    # These should always be lists
                    code_info[key] = value if isinstance(value, list) else []
                elif key in ["manifestation_properties", "scale_info"]:
                    # These should always be dictionaries
                    code_info[key] = value if isinstance(value, dict) else {}
                else:
                    # String fields - keep as string, even if empty
                    code_info[key] = value if value else ""

        return code_info

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
    # code_filter = None

    # Option 2: Extract only codes starting with specific prefixes
    # code_filter = "1"               # Codes starting with 1 (e.g., 1A00, 1C44, 1F25)
    # code_filter = "1A0"  # Codes starting with 1A0 (e.g., 1A00, 1A01, 1A02)
    code_filter = [
        "XM0061",
        "XM00E9",
        "XM00H9",
        "XM00Z1",
        "XM0179",
        "XM01R0",
        "XM01R5",
        "XM0232",
        "XM02T2",
        "XM0366",
        "XM0386",
        "XM03C0",
        "XM04B0",
        "XM05F4",
        "XM07P7",
        "XM0891",
        "XM08L6",
        "XM0907",
        "XM0AK0",
        "XM0AM0",
        "XM0B41",
        "XM0B62",
        "XM0BC6",
        "XM0BM0",
        "XM0BS2",
        "XM0BY4",
        "XM0C04",
        "XM0D44",
        "XM0DR1",
        "XM0EC2",
        "XM0EH6",
        "XM0ES5",
        "XM0EX6",
        "XM0FJ0",
        "XM0FK9",
        "XM0FY1",
        "XM0G40",
        "XM0G58",
        "XM0G86",
        "XM0GB3",
        "XM0GT6",
        "XM0JJ6",
        "XM0K92",
        "XM0KE3",
        "XM0KG9",
        "XM0L39",
        "XM0LP4",
        "XM0M17",
        "XM0M80",
        "XM0MD1",
        "XM0N40",
        "XM0NB5",
        "XM0PR3",
        "XM0PX4",
        "XM0QR2",
        "XM0QV6",
        "XM0QY7",
        "XM0QY9",
        "XM0R56",
        "XM0RZ0",
        "XM0SF4",
        "XM0SG7",
        "XM0TB3",
        "XM0TH7",
        "XM0TV9",
        "XM0TX8",
        "XM0V73",
        "XM0W28",
        "XM0WA6",
        "XM0WA9",
        "XM0WL1",
        "XM0XA8",
        "XM0XN7",
        "XM0XQ4",
        "XM0XS0",
        "XM0XT5",
        "XM0Y98",
        "XM0YQ4",
        "XM0Z74",
        "XM0ZH6",
        "XM1021",
        "XM11G0",
        "XM12H2",
        "XM1363",
        "XM1418",
        "XM14Y1",
        "XM1545",
        "XM1663",
        "XM16M2",
        "XM16M4",
        "XM16X6",
        "XM1762",
        "XM17F2",
        "XM17Q5",
        "XM1947",
        "XM1992",
        "XM19G9",
        "XM19S7",
        "XM1A56",
        "XM1A88",
        "XM1AE1",
        "XM1AE2",
        "XM1AF0",
        "XM1AH4",
        "XM1AU2",
        "XM1BL4",
        "XM1D37",
        "XM1D48",
        "XM1DV5",
        "XM1E24",
        "XM1EM9",
        "XM1EQ5",
        "XM1EY0",
        "XM1FG4",
        "XM1FN8",
        "XM1FQ3",
        "XM1FY5",
        "XM1GH9",
        "XM1GJ1",
        "XM1HE9",
        "XM1J33",
        "XM1JF3",
        "XM1JM2",
        "XM1KF1",
        "XM1L02",
        "XM1LD8",
        "XM1LE7",
        "XM1LN6",
        "XM1M89",
        "XM1MB6",
        "XM1MV4",
        "XM1MY0",
        "XM1N69",
        "XM1NS5",
        "XM1NV2",
        "XM1P52",
        "XM1PK2",
        "XM1PM8",
        "XM1PQ5",
        "XM1S86",
        "XM1TB2",
        "XM1TW0",
        "XM1UC6",
        "XM1UJ5",
        "XM1UP9",
        "XM1VX3",
        "XM1WT1",
        "XM1X04",
        "XM1X35",
        "XM1XL9",
        "XM1XZ4",
        "XM1YR6",
        "XM1YU1",
        "XM1ZR2",
        "XM21J6",
        "XM21W4",
        "XM23X0",
        "XM23X2",
        "XM23X8",
        "XM24L3",
        "XM2598",
        "XM26G6",
        "XM2732",
        "XM2738",
        "XM27U4",
        "XM27Y3",
        "XM27Z5",
        "XM28H1",
        "XM29D2",
        "XM29R2",
        "XM29X5",
        "XM2AE9",
        "XM2AZ6",
        "XM2BB9",
        "XM2BC0",
        "XM2BC2",
        "XM2BD5",
        "XM2BE5",
        "XM2BF4",
        "XM2BH3",
        "XM2BQ5",
        "XM2BX6",
        "XM2C70",
        "XM2CE0",
        "XM2CE3",
        "XM2D79",
        "XM2E62",
        "XM2EK4",
        "XM2EK8",
        "XM2FU2",
        "XM2FV2",
        "XM2G85",
        "XM2GY2",
        "XM2H01",
        "XM2HH5",
        "XM2HX1",
        "XM2JX3",
        "XM2KF5",
        "XM2KQ2",
        "XM2KR7",
        "XM2N89",
        "XM2NF0",
        "XM2PV9",
        "XM2Q78",
        "XM2QW2",
        "XM2R16",
        "XM2RB2",
        "XM2RH1",
        "XM2SG3",
        "XM2TA7",
        "XM2TV3",
        "XM2VA4",
        "XM2VG9",
        "XM2VY1",
        "XM2W36",
        "XM2W93",
        "XM2WR7",
        "XM2X16",
        "XM2X70",
        "XM2XU7",
        "XM2YA2",
        "XM2YN7",
        "XM2YX0",
        "XM2Z22",
        "XM2ZT3",
        "XM30V1",
        "XM31J1",
        "XM32L9",
        "XM33X3",
        "XM34N7",
        "XM34P0",
        "XM34R5",
        "XM36C7",
        "XM3709",
        "XM3757",
        "XM3834",
        "XM38G1",
        "XM38W0",
        "XM38Z7",
        "XM39E8",
        "XM39J1",
        "XM39J4",
        "XM3AF3",
        "XM3AP0",
        "XM3AW0",
        "XM3B42",
        "XM3BY9",
        "XM3CK7",
        "XM3CP7",
        "XM3D40",
        "XM3DA8",
        "XM3DP9",
        "XM3DX7",
        "XM3EA9",
        "XM3EF0",
        "XM3ES0",
        "XM3FJ3",
        "XM3FY4",
        "XM3FY5",
        "XM3FZ1",
        "XM3FZ9",
        "XM3G46",
        "XM3G74",
        "XM3JF2",
        "XM3KE4",
        "XM3KT4",
        "XM3LC5",
        "XM3M65",
        "XM3M91",
        "XM3M96",
        "XM3MD8",
        "XM3MM6",
        "XM3NB3",
        "XM3NC8",
        "XM3NH9",
        "XM3NJ2",
        "XM3NK1",
        "XM3NZ9",
        "XM3PV6",
        "XM3Q99",
        "XM3QE1",
        "XM3QL7",
        "XM3QP5",
        "XM3R78",
        "XM3TN8",
        "XM3VB6",
        "XM3VN8",
        "XM3XH8",
        "XM3XT1",
        "XM3YZ8",
        "XM40N4",
        "XM4321",
        "XM43H5",
        "XM44P3",
        "XM45E1",
        "XM46N0",
        "XM46Y1",
        "XM4882",
        "XM49C3",
        "XM49V0",
        "XM4AC2",
        "XM4BW2",
        "XM4BY7",
        "XM4CB0",
        "XM4CB3",
        "XM4CK0",
        "XM4L76",
        "XM4MR7",
        "XM4NS6",
        "XM4R06",
        "XM4S70",
        "XM4TE3",
        "XM4TF9",
        "XM4TJ7",
        "XM4TX6",
        "XM4UC8",
        "XM4UE4",
        "XM4UG8",
        "XM4W45",
        "XM4XS8",
        "XM4XU4",
        "XM4Y73",
        "XM4YD3",
        "XM4YU7",
        "XM4Z80",
        "XM5039",
        "XM5071",
        "XM50A4",
        "XM50B6",
        "XM5151",
        "XM5174",
        "XM52C3",
        "XM52C5",
        "XM53B3",
        "XM53K7",
        "XM5421",
        "XM5490",
        "XM54H2",
        "XM54Q3",
        "XM54V0",
        "XM5567",
        "XM55K4",
        "XM55M8",
        "XM55X0",
        "XM56G1",
        "XM56Q2",
        "XM56R9",
        "XM56V2",
        "XM5804",
        "XM58E5",
        "XM58G8",
        "XM58Q9",
        "XM58V1",
        "XM5911",
        "XM59S9",
        "XM59W8",
        "XM59Y7",
        "XM5AK0",
        "XM5AM5",
        "XM5B21",
        "XM5BM9",
        "XM5C83",
        "XM5CA9",
        "XM5D25",
        "XM5DJ5",
        "XM5E65",
        "XM5EH9",
        "XM5EL7",
        "XM5F09",
        "XM5F24",
        "XM5F38",
        "XM5FS3",
        "XM5FV8",
        "XM5GN1",
        "XM5H13",
        "XM5H65",
        "XM5HR7",
        "XM5HW4",
        "XM5HX1",
        "XM5J78",
        "XM5KH2",
        "XM5KR7",
        "XM5L03",
        "XM5L21",
        "XM5LE8",
        "XM5LH2",
        "XM5MK6",
        "XM5NA2",
        "XM5NH2",
        "XM5P41",
        "XM5Q94",
        "XM5U84",
        "XM5V50",
        "XM5W16",
        "XM5W67",
        "XM5WG7",
        "XM5WR8",
        "XM5X38",
        "XM5XP8",
        "XM5Y11",
        "XM5YT6",
        "XM5YV2",
        "XM5YV7",
        "XM5ZF9",
        "XM5ZJ4",
        "XM6000",
        "XM6076",
        "XM61M4",
        "XM63C5",
        "XM63U8",
        "XM6635",
        "XM66Z7",
        "XM6709",
        "XM67F1",
        "XM6859",
        "XM6882",
        "XM68C9",
        "XM6A31",
        "XM6A87",
        "XM6CP3",
        "XM6DJ2",
        "XM6EB1",
        "XM6FE5",
        "XM6FQ2",
        "XM6FX9",
        "XM6GM2",
        "XM6GU7",
        "XM6H15",
        "XM6HP7",
        "XM6HZ8",
        "XM6KR6",
        "XM6LL4",
        "XM6LL5",
        "XM6NP0",
        "XM6PE4",
        "XM6PY1",
        "XM6QA5",
        "XM6QH4",
        "XM6U93",
        "XM6UK4",
        "XM6VH6",
        "XM6W91",
        "XM6WF4",
        "XM6X33",
        "XM6XV7",
        "XM6XW9",
        "XM6YA3",
        "XM6Z57",
        "XM6ZJ9",
        "XM7134",
        "XM72P9",
        "XM73Y7",
        "XM74S8",
        "XM75C9",
        "XM76A0",
        "XM76E2",
        "XM76G6",
        "XM76X5",
        "XM7762",
        "XM77E6",
        "XM77Q2",
        "XM78T5",
        "XM79V9",
        "XM7AX9",
        "XM7B39",
        "XM7B62",
        "XM7BA0",
        "XM7BE0",
        "XM7CA8",
        "XM7CM2",
        "XM7CN5",
        "XM7CR8",
        "XM7CX7",
        "XM7CZ8",
        "XM7DD6",
        "XM7ED8",
        "XM7EL5",
        "XM7FG4",
        "XM7FZ2",
        "XM7JG0",
        "XM7JJ2",
        "XM7JK8",
        "XM7K06",
        "XM7K88",
        "XM7KB7",
        "XM7KY1",
        "XM7LD9",
        "XM7MB5",
        "XM7MJ9",
        "XM7MT6",
        "XM7N15",
        "XM7NR0",
        "XM7P94",
        "XM7QN7",
        "XM7QX9",
        "XM7RG5",
        "XM7S87",
        "XM7TE7",
        "XM7TN8",
        "XM7TP8",
        "XM7U05",
        "XM7U59",
        "XM7U84",
        "XM7UJ7",
        "XM7UN8",
        "XM7UW8",
        "XM7W63",
        "XM7WM1",
        "XM81B2",
        "XM81T5",
        "XM82G2",
        "XM82H0",
        "XM82K6",
        "XM82Y6",
        "XM83G3",
        "XM83H3",
        "XM83X7",
        "XM84E3",
        "XM84R4",
        "XM85A8",
        "XM86L8",
        "XM87D0",
        "XM87D3",
        "XM88J8",
        "XM88M1",
        "XM88U7",
        "XM89Q2",
        "XM8A62",
        "XM8AA6",
        "XM8AZ9",
        "XM8B44",
        "XM8B47",
        "XM8BF5",
        "XM8H37",
        "XM8HV3",
        "XM8JX9",
        "XM8M07",
        "XM8MB5",
        "XM8MF4",
        "XM8PU3",
        "XM8PV1",
        "XM8PX9",
        "XM8QC3",
        "XM8R10",
        "XM8R64",
        "XM8SE2",
        "XM8TE5",
        "XM8U54",
        "XM8UA9",
        "XM8VJ2",
        "XM8VR0",
        "XM8VV0",
        "XM8VV3",
        "XM8WE9",
        "XM8XU3",
        "XM8YH8",
        "XM8YX9",
        "XM8ZH3",
        "XM90H5",
        "XM90P2",
        "XM90U0",
        "XM90X8",
        "XM91A0",
        "XM91N3",
        "XM91T0",
        "XM91V9",
        "XM9217",
        "XM9359",
        "XM9524",
        "XM9588",
        "XM95D5",
        "XM95E9",
        "XM95L9",
        "XM95M5",
        "XM9834",
        "XM98M9",
        "XM98Y1",
        "XM98Z3",
        "XM99B7",
        "XM99Y1",
        "XM9A95",
        "XM9B14",
        "XM9B73",
        "XM9B82",
        "XM9BN0",
        "XM9BX0",
        "XM9C09",
        "XM9C47",
        "XM9CQ1",
        "XM9CV4",
        "XM9CZ8",
        "XM9DJ3",
        "XM9EQ8",
        "XM9F73",
        "XM9F85",
        "XM9GV7",
        "XM9GX9",
        "XM9HC2",
        "XM9HN7",
        "XM9JS2",
        "XM9KC4",
        "XM9KE6",
        "XM9KW2",
        "XM9L39",
        "XM9LD3",
        "XM9MV5",
        "XM9P91",
        "XM9QZ9",
        "XM9S25",
        "XM9T69",
        "XM9TZ1",
        "XM9UE9",
        "XM9UH2",
        "XM9UX0",
        "XM9W70",
        "XM9WJ0",
        "XM9WK6",
        "XM9WW6",
        "XM9YD2",
        "XM9YJ8",
        "XM9Z08",
        "XM9Z51",
        "XM9ZV3",
    ]

    # === CHAPTER FILTERING ===
    # Option 1: Extract from ALL chapters
    chapter_filter = ["Extension Codes"]

    # Option 2: Extract from specific chapters by number
    # chapter_filter = 1  # Chapter 1: Certain infectious or parasitic diseases
    # chapter_filter = ["severty scale value"]

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

        filename = "icd11_missing_substances.json"

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

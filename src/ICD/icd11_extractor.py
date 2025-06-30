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

    pass

import json
import os


def get_icd_description(
    icd_code, json_file_path="./icd11_all_codes_chapter_1_all_digits.json"
):
    """
    Extract and format all available information for a given ICD-11 code.

    Args:
        icd_code (str): The ICD-11 code to search for (e.g., "1A00")

    Returns:
        str: A formatted string containing all available information for the ICD code,
             or None if the code is not found
    """
    try:
        # Load the JSON data
        with open(json_file_path, "r", encoding="utf-8") as file:
            icd_data = json.load(file)

        # Search for the matching code
        for entry in icd_data:
            if entry.get("code") == icd_code:
                # Build the formatted string
                result_parts = []

                # Add code
                result_parts.append(f"code: {entry.get('code', 'N/A')}")

                # Add title
                result_parts.append(f"title: {entry.get('title', 'N/A')}")

                # Add fully_specified_name if it exists
                if entry.get("fully_specified_name"):
                    result_parts.append(
                        f"fully_specified_name: {entry.get('fully_specified_name')}"
                    )

                # Add definition if it exists
                if entry.get("definition"):
                    result_parts.append(f"definition: {entry.get('definition')}")

                # Add inclusions if they exist and are not empty
                if entry.get("inclusions") and len(entry.get("inclusions", [])) > 0:
                    inclusions_str = ", ".join(entry.get("inclusions", []))
                    result_parts.append(f"inclusions: {inclusions_str}")

                # Add all_labels if they exist and are not empty
                if entry.get("all_labels") and len(entry.get("all_labels", [])) > 0:
                    all_labels_str = ", ".join(entry.get("all_labels", []))
                    result_parts.append(f"all_labels: {all_labels_str}")

                # Add parent_info if it exists and is not empty
                if entry.get("parent_info") and len(entry.get("parent_info", [])) > 0:
                    parent_info_parts = []
                    for parent in entry.get("parent_info", []):
                        parent_str = f"title: {parent.get('title', 'N/A')}"
                        if parent.get("code"):
                            parent_str = f"code: {parent.get('code')}, " + parent_str
                        if parent.get("definition"):
                            parent_str += f", definition: {parent.get('definition')}"
                        parent_info_parts.append(f"({parent_str})")
                    result_parts.append(f"parent_info: {'; '.join(parent_info_parts)}")

                # Add browser_url if it exists
                if entry.get("browser_url"):
                    result_parts.append(f"browser_url: {entry.get('browser_url')}")

                # Join all parts with ", "
                return ", ".join(result_parts)

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

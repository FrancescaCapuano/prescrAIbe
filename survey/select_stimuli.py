import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "retrieval"))

from interaction_matrix import InteractionMatrixBuilder
import json
import random


def load_interaction_matrix():
    """
    Load the interaction matrix using the InteractionMatrixBuilder.

    Returns:
        dict: Loaded interaction matrix
    """
    # Initialize the matrix builder
    matrix_builder = InteractionMatrixBuilder()

    # Load the matrix from the default location
    matrix_file = "data/interaction_matrix/interaction_matrix.json"

    try:
        print(f"📂 Loading interaction matrix from: {matrix_file}")
        matrix = matrix_builder.load_matrix(matrix_file)
        print(f"✅ Successfully loaded {len(matrix)} interaction pairs")
        return matrix
    except FileNotFoundError:
        print(f"❌ Matrix file not found: {matrix_file}")
        return None
    except Exception as e:
        print(f"❌ Error loading matrix: {e}")
        return None


def get_sample_interactions(matrix, n_samples=10):
    """
    Get a sample of interactions from the matrix for the survey.

    Args:
        matrix (dict): The loaded interaction matrix
        n_samples (int): Number of samples to select

    Returns:
        list: List of sample interactions with contraindication and ICD info
    """
    if not matrix:
        return []

    # Get all available pairs
    all_pairs = list(matrix.keys())

    # Sample random pairs
    sampled_pairs = random.sample(all_pairs, min(n_samples, len(all_pairs)))

    survey_items = []
    for pair_key in sampled_pairs:
        # Split the key to get AIC and ICD
        if "|" in pair_key:
            aic_code, icd_code = pair_key.split("|", 1)

            # Get the interactions for this pair
            interactions = matrix[pair_key]

            if interactions:
                # Take the first interaction as an example
                interaction = interactions[0]

                survey_item = {
                    "aic_code": aic_code,
                    "aic_url": interaction.get("aic_url", ""),
                    "icd_code": icd_code,
                    "warning": interaction.get("warning", ""),
                    "icd_name": interaction.get("icd_name", ""),
                    "icd_url": interaction.get("icd_url", ""),
                    "pair_key": pair_key,
                }
                survey_items.append(survey_item)

    return survey_items


def save_as_js_file(survey_items, output_file="test_stimuli.js"):
    """
    Save survey items as a JavaScript file with the correct format.

    Args:
        survey_items (list): List of survey items
        output_file (str): Output JavaScript file name
    """
    js_content = "var test_stimuli = [\n"

    for i, item in enumerate(survey_items):
        # Escape quotes and format the stimulus
        contraindication = item["warning"].replace('"', '\\"').replace("'", "\\'")
        icd_name = item["icd_name"].replace('"', '\\"').replace("'", "\\'")
        aic_url = item["aic_url"].replace('"', '\\"').replace("'", "\\'")
        icd_url = item["icd_url"].replace('"', '\\"').replace("'", "\\'")

        stimulus_html = f"""    {{
        stimulus: `
            <div style="padding: 20px; max-width: 600px; margin: 0 auto;">
                <p><strong>Controindicazione:</strong> {contraindication}</p>
                <p style="font-size: 12px; margin-top: 5px;"><a href="{aic_url}" target="_blank" style="color: #666; text-decoration: underline;">{aic_url}</a></p>
                <p><strong>ICD:</strong> {icd_name}</p>
                <p style="font-size: 12px; margin-top: 5px;"><a href="{icd_url}" target="_blank" style="color: #666; text-decoration: underline;">{icd_url}</a></p>
            </div>
        `
    }}"""

        js_content += stimulus_html

        # Add comma if not the last item
        if i < len(survey_items) - 1:
            js_content += ",\n"
        else:
            js_content += "\n"

    js_content += "];"

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"💾 Saved {len(survey_items)} stimuli to: {output_file}")


def main():
    """
    Main function to load matrix and prepare survey items.
    """
    print("🚀 Loading interaction matrix for survey...")

    # Load the interaction matrix
    matrix = load_interaction_matrix()

    if matrix:
        # Get some sample interactions
        sample_items = get_sample_interactions(matrix, n_samples=20)

        print(f"\n📋 Selected {len(sample_items)} items for survey:")
        for i, item in enumerate(sample_items[:5], 1):  # Show first 5
            print(f"   {i}. AIC: {item['aic_code']}")
            print(f"      ICD: {item['icd_code']}")
            print(f"      Contraindication: {item['warning'][:100]}...")
            print(f"      ICD Description: {item['icd_name'][:100]}...")
            print()

        # Save sample items as JavaScript file
        save_as_js_file(sample_items, "survey/test_stimuli.js")

        return sample_items
    else:
        print("❌ Could not load interaction matrix")
        return []


if __name__ == "__main__":
    main()

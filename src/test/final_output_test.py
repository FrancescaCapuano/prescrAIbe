import pandas as pd
import json
from pathlib import Path
from collections import defaultdict


def prepare_test(ground_truth: pd.DataFrame):
    test_cases = defaultdict(list)

    for index, row in ground_truth.iterrows():
        aic = row["drug (AIC)"]
        warning = str(row["map context to one correct ICD-cod (Step 3)"]).split()[0]
        no_warning = str(row["map context to one incorrect ICD-cod (Step 4)"]).split()[
            0
        ]

        # Fill aic with 0s to the left until length 9
        aic = str(aic).zfill(9)

        # If warning is not nan
        if pd.notna(warning) and warning != "nan":
            test_cases["warning"].append((aic, warning))
        if pd.notna(no_warning) and no_warning != "nan":
            test_cases["no_warning"].append((aic, no_warning))

    return test_cases


def run_test(test_cases, interaction_matrix):
    matches_warning = 0
    matches_no_warning = 0

    for aic, icd_code in test_cases["warning"]:
        # Check if the AIC exists in the interaction matrix
        test_case_as_key = f"{aic}|{icd_code}"

        # If the key exists in the interaction matrix, it's a match
        if test_case_as_key in interaction_matrix.keys():
            matches_warning += 1

    for aic, icd_code in test_cases["no_warning"]:
        # Check if the AIC exists in the interaction matrix
        test_case_as_key = f"{aic}|{icd_code}"

        # If the key exists in the interaction matrix, it's a match
        if test_case_as_key not in interaction_matrix.keys():
            matches_no_warning += 1

    print(
        f"Percentage of matches: {matches_warning / len(test_cases['warning']) * 100:.2f}%"
    )
    print(
        f"Percentage of no matches: {matches_no_warning / len(test_cases['no_warning']) * 100:.2f}%"
    )


if __name__ == "__main__":
    # Load the ground truth data
    ground_truth = pd.read_excel("../../data/ground_truth/ground_truth.xlsx")

    # Prepare test
    test = prepare_test(ground_truth)

    # Read interaction matrix json file - use json.load instead
    interaction_matrix_path = Path(
        "../../data/interaction_matrix/interaction_matrix.json"
    )

    with open(interaction_matrix_path, "r", encoding="utf-8") as f:
        interaction_matrix = json.load(f)

    print(f"Interaction matrix loaded with {len(interaction_matrix)} entries")

    # Run the test
    run_test(test, interaction_matrix)

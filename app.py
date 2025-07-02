import streamlit as st
import json
import pandas as pd

st.set_page_config(
    page_title="AI for Safer Prescriptions",
    page_icon="💊",  # This emoji will appear in the browser tab
)


# Load data
def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource
def load_all_data():
    interaction_matrix = load_json("data/interaction_matrix/interaction_matrix.json")
    icd11_database_raw = load_json("data/ICD-codes/icd11_database.json")
    if isinstance(icd11_database_raw, list):
        icd11_database = {
            item["code"]: item for item in icd11_database_raw if "code" in item
        }
    else:
        icd11_database = icd11_database_raw

    aic_codes = set()
    aic_icd_mapping = {}
    aic_name_map = {}

    for composite_key, warnings_list in interaction_matrix.items():
        if "|" in composite_key:
            aic_code, icd_code = composite_key.split("|", 1)
            aic_codes.add(aic_code)
            if aic_code not in aic_icd_mapping:
                aic_icd_mapping[aic_code] = {}
            aic_icd_mapping[aic_code][icd_code] = warnings_list
            # Extract AIC name from the first warning (assuming all warnings for this combo have the same AIC name)
            if warnings_list and aic_code not in aic_name_map:
                aic_name_map[aic_code] = warnings_list[0].get(
                    "AIC-code", "Name not found"
                )
    return (
        interaction_matrix,
        icd11_database,
        aic_name_map,
        sorted(list(aic_codes)),
        aic_icd_mapping,
    )


# Usage:
interaction_matrix, icd11_database, aic_name_map, aic_codes, aic_icd_mapping = (
    load_all_data()
)


def get_icd_display_name(icd_code, icd11_database):
    """Get display name for ICD code"""
    if icd_code in icd11_database:
        title = icd11_database[icd_code].get("title", "N/A")
        return f"{icd_code} - {title}"
    return f"{icd_code} - (Title not found)"


def get_aic_display_name(aic_code, aic_name_map):
    """Get display name for AIC code"""
    name = aic_name_map.get(aic_code, "Name not found")
    return f"{aic_code} - {name}"


# Sidebar with project info and instructions
st.sidebar.title("ICD11 Interaction Checker")
st.sidebar.markdown(
    """
**Project Information**
- This app checks for warnings based on selected AIC and ICD codes.
- Data sources: WHO ICD-classification, Leaflets from AIFA.

Contributors:
Francesca Capuano & Viktoria Leuschner
"""
)

# Main UI
st.title("💊 AI for Safer Prescriptions")

# First dropdown: ICD codes (all available ICD codes)
icd_options = [
    get_icd_display_name(code, icd11_database) for code in sorted(icd11_database.keys())
]
selected_icd_displays = st.multiselect(
    "Select ICD11 Codes", options=icd_options, key="icd_selector"
)

# Extract ICD codes from display names
selected_icds = [display.split(" - ")[0] for display in selected_icd_displays]

# Second dropdown: AIC codes with names
aic_options = [get_aic_display_name(code, aic_name_map) for code in aic_codes]
selected_aic_display = st.selectbox(
    "Select AIC Code", options=[""] + aic_options, index=0, key="aic_selector"
)
selected_aic = selected_aic_display.split(" - ")[0] if selected_aic_display else ""

if selected_aic and selected_icds:

    # Create a results table
    results = []

    for icd in selected_icds:
        # Check if this AIC-ICD combination exists in our mapping
        warnings_data = aic_icd_mapping.get(selected_aic, {}).get(icd, [])

        if warnings_data:
            for warning_item in warnings_data:
                results.append(
                    {
                        "AIC Code": selected_aic,
                        "AIC Name": aic_name_map.get(selected_aic, "Name not found"),
                        "ICD Code": icd,
                        "ICD Name": icd11_database.get(icd, {}).get("title", "N/A"),
                        "Warning (Italian)": warning_item.get("warning", "N/A"),
                        "AIC URL": warning_item.get("aic_url", "N/A"),
                    }
                )
        else:
            results.append(
                {
                    "AIC Code": selected_aic,
                    "AIC Name": aic_name_map.get(selected_aic, "Name not found"),
                    "ICD Code": icd,
                    "ICD Name": icd11_database.get(icd, {}).get("title", "N/A"),
                    "Warning (Italian)": "No warning",
                    "AIC URL": "N/A",
                }
            )

    if results:
        # Remove the table summary of warnings (no st.dataframe)
        # Only display warnings in a more readable format
        st.subheader("Warnings")
        warning_found = False
        for result in results:
            if result["Warning (Italian)"] != "No warning":
                st.warning(
                    f"""
                **AIC {result['AIC Code']} ({result['AIC Name']}) + ICD {result['ICD Code']} ({result['ICD Name']})**
                
                {result['Warning (Italian)']}
                
                [View AIC Details]({result['AIC URL']})
                """
                )
                warning_found = True

        if not warning_found:
            st.success("✅ No warnings found for the selected combination.")

elif selected_aic and not selected_icds:
    st.info("Please select at least one ICD11 code to check for interactions.")
elif not selected_aic and selected_icds:
    st.info("Please select an AIC code to check for interactions.")
else:
    st.info("Please select an AIC code and at least one ICD11 code to view warnings.")

# Debug information (expandable)
with st.expander("Debug Information"):
    st.write(f"Total AIC codes available: {len(aic_codes)}")
    st.write(f"Total ICD codes available: {len(icd11_database)}")
    st.write(f"Total interaction combinations: {len(interaction_matrix)}")

    if selected_aic:
        available_icds_for_aic = list(aic_icd_mapping.get(selected_aic, {}).keys())
        st.write(
            f"ICD codes with interactions for AIC {selected_aic}: {len(available_icds_for_aic)}"
        )
        if available_icds_for_aic:
            st.write(
                "Available ICD codes for this AIC:", available_icds_for_aic[:10]
            )  # Show first 10

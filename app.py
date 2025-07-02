import streamlit as st
import json
import pandas as pd

# Import the InteractionMatrixBuilder class
from src.retrieval.interaction_matrix import InteractionMatrixBuilder

st.set_page_config(
    page_title="AI for Safer Prescriptions",
    page_icon="💊",  # This emoji will appear in the browser tab
)


# Load data using InteractionMatrixBuilder
@st.cache_resource
def load_all_data():
    # Initialize the builder
    matrix_builder = InteractionMatrixBuilder()
    # Load the interaction matrix from file
    interaction_matrix = matrix_builder.load_matrix(
        "data/interaction_matrix/interaction_matrix.json"
    )

    # Load the new ICD11 vector DB
    with open(
        "data/ICD-codes/icd11_vectordb_base_compressed.json", "r", encoding="utf-8"
    ) as f:
        icd11_vectordb = json.load(f)
    # Build icd11_database from vectordb
    icd11_database = {}
    for entry in icd11_vectordb:
        url = entry.get("url", "")
        name = entry.get("name", "")  # Use the 'name' field for the title
        if "#" in url:
            code = url.split("#")[-1].split("/")[0]
            icd11_database[code] = {
                "code": code,
                "url": url,
                "title": name,  # Use the name as the title
            }

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
                # Try to get AIC name from the matrix entry, fallback to code
                aic_name_map[aic_code] = warnings_list[0].get(
                    "aic_name", warnings_list[0].get("AIC-code", "Name not found")
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
        # Use code as title, since no title in vectordb
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


# Load patient-ICD mapping (now includes ICD-11 name)
@st.cache_data
def load_patient_icd_mapping(csv_path):
    df = pd.read_csv(csv_path, sep=";")
    df = df.dropna(subset=["patient", "ICD 11 code"])
    # Build mapping: patient -> list of (ICD 11 code, ICD 11 name)
    patient_icd_map = (
        df.groupby("patient")[["ICD 11 code", "ICD 11 text"]]
        .apply(lambda x: sorted(set(tuple(row) for row in x.values)))
        .to_dict()
    )
    return patient_icd_map, sorted(patient_icd_map.keys())


patient_icd_map, patient_list = load_patient_icd_mapping(
    "data/patients/snomed_icd_mapping.csv"
)

# Main UI
st.title("💊 AI for Safer Prescriptions")

# Patient selector in the main area
selected_patient = st.selectbox(
    "Select Patient", [""] + patient_list, key="main_patient_selector"
)

# Show ICD-11 codes and names for the selected patient (from CSV)
if selected_patient:
    patient_icd_tuples = patient_icd_map.get(selected_patient, [])
    # Filter out ICD codes containing "/"
    filtered_icd_tuples = [
        (code, name) for code, name in patient_icd_tuples if "/" not in str(code)
    ]
    if filtered_icd_tuples:
        icd_display_list = [
            f"- **{code}**: {name}" for code, name in filtered_icd_tuples
        ]
        st.markdown(
            "**ICD-11 codes for this patient:**\n\n" + "\n".join(icd_display_list)
        )
        patient_icd_codes = [code for code, name in filtered_icd_tuples]
    else:
        st.warning("No valid ICD-11 codes found for this patient.")
        patient_icd_codes = []
else:
    patient_icd_codes = []

# AIC code selector
aic_options = [get_aic_display_name(code, aic_name_map) for code in aic_codes]
selected_aic_display = st.selectbox(
    "Select AIC Code", options=[""] + aic_options, index=0, key="aic_selector"
)
selected_aic = selected_aic_display.split(" - ")[0] if selected_aic_display else ""

# Only check if both patient and AIC are selected
if selected_patient and selected_aic and patient_icd_codes:
    results = []
    for icd in patient_icd_codes:
        warnings_data = aic_icd_mapping.get(selected_aic, {}).get(icd, [])
        if warnings_data:
            for warning_item in warnings_data:
                results.append(
                    {
                        "AIC Code": selected_aic,
                        "AIC Name": aic_name_map.get(selected_aic, "Name not found"),
                        "ICD Code": icd,
                        "ICD Name": next(
                            (name for code, name in patient_icd_tuples if code == icd),
                            "N/A",
                        ),
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
                    "ICD Name": next(
                        (name for code, name in patient_icd_tuples if code == icd),
                        "N/A",
                    ),
                    "Warning (Italian)": "No warning",
                    "AIC URL": "N/A",
                }
            )
    if results:
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
elif selected_patient and not selected_aic:
    st.info("Please select an AIC code to check for interactions.")
elif selected_aic and not selected_patient:
    st.info("Please select a patient to check for interactions.")
else:
    st.info("Please select a patient and an AIC code to view warnings.")

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

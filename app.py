import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime

# Import the InteractionMatrixBuilder class
from src.retrieval.interaction_matrix import InteractionMatrixBuilder

st.set_page_config(
    page_title="PrescrAIbe",
    page_icon="💊",  # This emoji will appear in the browser tab
)

# Add custom title with styled AI
st.markdown(
    """
    <h1 style='text-align: left'>
        💊 Prescr<span style='color: #FF8C00'>AI</span>be
    </h1>
    """,
    unsafe_allow_html=True,
)


# First, load the drug names from the Excel file
def load_drug_names():
    drug_names = {}
    try:
        # Read Excel file with explicit data types
        df = pd.read_excel(
            "data/leaflets/estrazione_farmaci_downloaded.xlsx",
            dtype={
                "code": str,  # Force code column to be string
                "name": str,  # Force name column to be string
            },
        )

        # Clean the data
        df["code"] = df["code"].astype(str).str.strip()
        df["name"] = df["name"].astype(str).str.strip()

        # Remove any rows where code or name is empty/null
        df = df.dropna(subset=["code", "name"])

        # Create mapping from AIC code to name
        for _, row in df.iterrows():
            code = str(row["code"]).strip()
            name = str(row["name"]).strip()
            if code and name:  # Only add if both code and name are non-empty
                drug_names[code] = name

    except Exception as e:
        st.error(f"Error loading drug names from Excel: {e}")
        return {}

    return drug_names


# Load data using InteractionMatrixBuilder
@st.cache_resource
def load_all_data():
    # Initialize the builder
    matrix_builder = InteractionMatrixBuilder()
    # Load the interaction matrix from file
    interaction_matrix = matrix_builder.load_matrix(
        "data/interaction_matrix/interaction_matrix.json"
    )

    # Load drug names from CSV
    aic_name_map = load_drug_names()

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

    for composite_key, warnings_list in interaction_matrix.items():
        if "|" in composite_key:
            aic_code, icd_code = composite_key.split("|", 1)
            aic_codes.add(aic_code)
            if aic_code not in aic_icd_mapping:
                aic_icd_mapping[aic_code] = {}
            aic_icd_mapping[aic_code][icd_code] = warnings_list

    return (
        interaction_matrix,
        icd11_database,
        aic_name_map,
        sorted(list(aic_codes)),
        aic_icd_mapping,
        icd11_vectordb,
    )


# Usage:
(
    interaction_matrix,
    icd11_database,
    aic_name_map,
    aic_codes,
    aic_icd_mapping,
    icd11_vectordb,
) = load_all_data()


# Add this function after the load_all_data() function
def save_feedback(feedback_data):
    """Save feedback to JSON file"""
    feedback_file = "data/feedback/warning_feedback.json"
    os.makedirs(os.path.dirname(feedback_file), exist_ok=True)

    # Load existing feedback
    if os.path.exists(feedback_file):
        with open(feedback_file, "r") as f:
            existing_feedback = json.load(f)
    else:
        existing_feedback = []

    # Add new feedback
    existing_feedback.append(feedback_data)

    # Save updated feedback
    with open(feedback_file, "w") as f:
        json.dump(existing_feedback, f, indent=2)


def find_safe_alternatives(aic_code, patient_icd_codes, aic_name_map, aic_icd_mapping):
    """
    Find alternative drugs that have no warnings for the patient's conditions.

    Args:
        aic_code (str): Current AIC code that has warnings
        patient_icd_codes (list): List of patient's ICD codes
        aic_name_map (dict): Mapping of AIC codes to names
        aic_icd_mapping (dict): Mapping of AIC-ICD combinations to warnings

    Returns:
        list: List of tuples (aic_code, aic_name) of safe alternatives
    """
    # Load alternatives matrix
    try:
        with open("data/drug_alternatives_matrix/drug_alternatives.json", "r") as f:
            alternatives_matrix = json.load(f)
    except Exception as e:
        st.error(f"Error loading alternatives matrix: {e}")
        return []

    # Get alternative drugs for the current AIC code
    alternatives = alternatives_matrix.get(aic_code, [])
    if not alternatives:
        return []

    safe_alternatives = []

    # Load the URLs from interaction matrix
    try:
        with open(
            "data/interaction_matrix/interaction_matrix.json", "r", encoding="utf-8"
        ) as f:
            interaction_matrix = json.load(f)
    except Exception as e:
        st.error(f"Error loading interaction matrix: {e}")
        return []

    # Check each alternative drug
    for alt_aic in alternatives:
        is_safe = True

        # Skip if it's the same as the current drug
        if alt_aic == aic_code:
            continue

        # Check if alternative has no warnings for any of patient's conditions
        if alt_aic in aic_icd_mapping:
            for icd_code in patient_icd_codes:
                warnings = aic_icd_mapping[alt_aic].get(icd_code, [])
                for warning in warnings:
                    if (
                        warning.get("warning", "")
                        != "Based on the information of the drug leaflet and the condition(s), no contraindication has been found."
                    ):
                        is_safe = False
                        break
                if not is_safe:
                    break

        # If safe, add to list with its name
        if is_safe:
            alt_name = aic_name_map.get(alt_aic, "Name not found")
            # Get URL from any warning entry for this drug
            url = None
            for key, warnings in interaction_matrix.items():
                if key.startswith(alt_aic + "|"):
                    for warning in warnings:
                        if "aic_url" in warning:
                            url = warning["aic_url"]
                            break
                    if url:
                        break
            safe_alternatives.append((alt_aic, alt_name, url))

    return safe_alternatives


def get_icd_display_name(icd_code, icd11_database):
    """Get display name for ICD code"""
    if icd_code in icd11_database:
        # Use code as title, since no title in vectordb
        title = icd11_database[icd_code].get("title", "N/A")
        return f"{icd_code} - {title}"
    return f"{icd_code} - (Title not found)"


def get_aic_display_name(aic_code, aic_name_map):
    """Get display name for AIC code"""
    # Convert aic_code to string and strip any whitespace
    aic_code = str(aic_code).strip()
    # Get the name from aic_name_map, default to "Name not found" if not found
    name = aic_name_map.get(aic_code, "Name not found")
    return f"{aic_code} - {name}"


# Sidebar with project info and instructions
st.sidebar.markdown(
    """
**Project Information** \n
This app checks for contraindications between existing conditions and drugs, that are prescibed by doctors. It was developed at Data Science Retreat.

**Contributors**: \n
Francesca Capuano & Viktoria Leuschner
"""
)

# Add this after the sidebar project info section
st.sidebar.markdown("---")  # Add a separator
enable_feedback = st.sidebar.checkbox("Enable Warning Feedback", value=False)

# Add this after the existing enable_feedback checkbox
st.sidebar.markdown("---")  # Add another separator
show_active_only = st.sidebar.checkbox("Persisting Conditions", value=False)

# Add this at the beginning of your script after the imports
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = set()


# Load patient-ICD mapping (now includes ICD-11 name)
@st.cache_data
def load_patient_icd_mapping(csv_path):
    df = pd.read_csv(csv_path, sep=";")
    df = df.dropna(subset=["patient", "ICD 11 code"])
    # Convert date columns to datetime for sorting
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["abatement date"] = pd.to_datetime(df["abatement date"], errors="coerce")
    # Build mapping: patient -> list of (ICD 11 code, ICD 11 name, date, abatement date)
    patient_icd_map = (
        df.sort_values("date")
        .groupby("patient")[["ICD 11 code", "ICD 11 text", "date", "abatement date"]]
        .apply(lambda x: [(row[0], row[1], row[2], row[3]) for row in x.values])
        .to_dict()
    )
    return patient_icd_map, sorted(patient_icd_map.keys())


patient_icd_map, patient_list = load_patient_icd_mapping(
    "data/patients/snomed_icd_mapping.csv"
)

# Patient selector in the main area
selected_patient = st.selectbox(
    "Select Patient", [""] + patient_list, key="main_patient_selector"
)

# Show ICD-11 codes and names for the selected patient (from CSV)
if selected_patient:
    patient_icd_tuples = patient_icd_map.get(selected_patient, [])
    # Filter out ICD codes containing "/"
    filtered_icd_tuples = [
        (code, name, date, abatement)
        for code, name, date, abatement in patient_icd_tuples
        if "/" not in str(code) and (not show_active_only or pd.isna(abatement))
    ]
    if filtered_icd_tuples:
        # Create a styled container for the patient card
        st.markdown(
            """
            <style>
            .patient-card {
                border: 1px solid #e1e4e8;
                border-radius: 10px;
                padding: 20px;
                margin: 10px 0;
                background-color: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .condition-entry {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
                padding: 8px;
                border-left: 3px solid #e1e4e8;  /* Light grey border for all conditions */
                padding-left: 10px;
            }
            .condition-header {
                background-color: #f6f8fa;
                padding: 10px;
                border-radius: 5px 5px 0 0;
                margin-bottom: 15px;
                border-bottom: 2px solid #e1e4e8;
            }
            .condition-info {
                flex-grow: 1;
                margin-right: 20px;
            }
            .condition-date {
                color: #586069;
                font-size: 0.9em;
                white-space: nowrap;
            }
            .icd-link {
                text-decoration: none !important;
                color: #333333 !important;  // Added !important to override browser defaults
            }
            .icd-link:hover {
                text-decoration: underline !important;
                color: #333333 !important;
            }
            .icd-link:visited {
                color: #333333 !important;  // Added to handle visited links
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Group conditions by date
        from collections import defaultdict

        date_groups = defaultdict(list)
        for code, name, date, abatement in filtered_icd_tuples:
            date_key = (
                date.strftime("%Y-%m-%d") if pd.notnull(date) else "N/A",
                abatement.strftime("%Y-%m-%d") if pd.notnull(abatement) else "",
            )
            date_groups[date_key].append((code, name))

        # Display conditions
        for date_str, abatement_str in sorted(date_groups.keys()):
            if abatement_str:
                date_display = f"{date_str} - {abatement_str}"
                condition_class = "condition-inactive"
            else:
                date_display = f"{date_str} - Present"
                condition_class = "condition-active"

            for code, name in date_groups[(date_str, abatement_str)]:
                matching_entry = next(
                    (entry for entry in icd11_vectordb if entry.get("code") == code),
                    None,
                )

                if matching_entry and "url" in matching_entry:
                    st.markdown(
                        f"""
                        <div class="condition-entry {condition_class}">
                            <div class="condition-info">
                                <a href="{matching_entry["url"]}" target="_blank" class="icd-link">
                                    <strong>{code}</strong>
                                </a>: {name}
                            </div>
                            <div class="condition-date">
                                {date_display}
                            </div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="condition-entry {condition_class}">
                            <div class="condition-info">
                                <strong>{code}</strong>: {name}
                            </div>
                            <div class="condition-date">
                                {date_display}
                            </div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )

        st.markdown("</div>", unsafe_allow_html=True)
        patient_icd_codes = [
            code
            for code, name, date, abatement in filtered_icd_tuples
            if not show_active_only or pd.isna(abatement)
        ]
    else:
        st.markdown(
            """
            <div style='padding: 1rem; border-radius: 0.5rem; background-color: #f0f2f6; color: #31333F'>
            No persistent conditions found for this patient.
            </div>
            """,
            unsafe_allow_html=True,
        )
        patient_icd_codes = []
else:
    patient_icd_codes = []

# AIC code selector
aic_options = [get_aic_display_name(code, aic_name_map) for code in aic_codes]
selected_aic_display = st.selectbox(
    "Select Drug",
    options=[""] + sorted(aic_options),  # Sort the options for better usability
    index=0,
    key="aic_selector",
)
selected_aic = selected_aic_display.split(" - ")[0] if selected_aic_display else ""


# Load the translated interaction matrix
@st.cache_resource
def load_translated_matrix():
    with open(
        "data/interaction_matrix/interaction_matrix_translated.json",
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


translated_matrix = load_translated_matrix()

# Only check if both patient and AIC are selected
if selected_patient and selected_aic and patient_icd_codes:
    results = []
    for icd in patient_icd_codes:
        warnings_data = aic_icd_mapping.get(selected_aic, {}).get(icd, [])
        if warnings_data:
            for warning_item in warnings_data:
                # Get English translation if available
                composite_key = f"{selected_aic}|{icd}"
                eng_warning = None
                if composite_key in translated_matrix:
                    translated_warnings = translated_matrix[composite_key]
                    for tw in translated_warnings:
                        if tw.get("warning", "") == warning_item.get("warning", ""):
                            eng_warning = tw.get("warning_eng")
                            break

                results.append(
                    {
                        "AIC Code": selected_aic,
                        "AIC Name": aic_name_map.get(selected_aic, "Name not found"),
                        "ICD Code": icd,
                        "ICD Name": next(
                            (
                                name
                                for code, name, date, abatement in patient_icd_tuples
                                if code == icd
                            ),
                            "N/A",
                        ),
                        "Warning (Italian)": warning_item.get("warning", "N/A"),
                        "Warning (English)": eng_warning,
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
                        (
                            name
                            for code, name, date, abatement in patient_icd_tuples
                            if code == icd
                        ),
                        "N/A",
                    ),
                    "Warning (Italian)": "Based on the information of the drug leaflet and the condition(s), no contraindication has been found.",
                    "Warning (English)": None,
                    "AIC URL": "N/A",
                }
            )

    if results:
        st.subheader("Warnings")
        warning_found = False

        # Group results by AIC-ICD combination
        grouped_results = {}
        for result in results:
            combination_key = f"{result['AIC Code']}_{result['ICD Code']}"
            if combination_key not in grouped_results:
                grouped_results[combination_key] = []
            grouped_results[combination_key].append(result)

        # Process each group of warnings
        for combination_key, group_results in grouped_results.items():
            has_warnings = False

            # Display all warnings for this combination
            for idx, result in enumerate(group_results):
                if (
                    result["Warning (Italian)"]
                    != "Based on the information of the drug leaflet and the condition(s), no contraindication has been found."
                ):
                    warning_found = True
                    has_warnings = True

                    # Display warning in a container
                    with st.container():
                        warning_text = f"""**{result['AIC Code']} ({result['AIC Name']}) + {result['ICD Code']} ({result['ICD Name']})**

**IT**: {result['Warning (Italian)']}"""

                        if result["Warning (English)"]:
                            warning_text += f"\n\n**EN**: {result['Warning (English)']}"

                        if result["AIC URL"] != "N/A":
                            warning_text += f"\n\n[View Leaflet]({result['AIC URL']})"

                        st.warning(warning_text)

                        # Only show feedback buttons if feedback is enabled and feedback hasn't been given
                        feedback_key = f"{result['AIC Code']}_{result['ICD Code']}_{hash(result['Warning (Italian)'])}"
                        if (
                            enable_feedback
                            and feedback_key not in st.session_state.feedback_given
                        ):
                            # Create unique keys for each warning's feedback buttons
                            accept_key = f"accept_{combination_key}_{idx}"
                            reject_key = f"reject_{combination_key}_{idx}"

                            # Add feedback buttons in columns
                            col1, col2, col3 = st.columns([1, 1, 3])
                            with col1:
                                if st.button("✅ Accept Warning", key=accept_key):
                                    feedback = {
                                        "timestamp": datetime.now().isoformat(),
                                        "aic_code": result["AIC Code"],
                                        "icd_code": result["ICD Code"],
                                        "warning": result["Warning (Italian)"],
                                        "feedback": "accepted",
                                    }
                                    save_feedback(feedback)
                                    st.session_state.feedback_given.add(feedback_key)
                                    st.success("Feedback saved - Warning Accepted")
                                    st.rerun()

                            with col2:
                                if st.button("❌ Reject Warning", key=reject_key):
                                    feedback = {
                                        "timestamp": datetime.now().isoformat(),
                                        "aic_code": result["AIC Code"],
                                        "icd_code": result["ICD Code"],
                                        "warning": result["Warning (Italian)"],
                                        "feedback": "rejected",
                                    }
                                    save_feedback(feedback)
                                    st.session_state.feedback_given.add(feedback_key)
                                    st.success("Feedback saved - Warning Rejected")
                                    st.rerun()

            # After displaying all warnings for this combination, show alternatives if there were any warnings
            if has_warnings:
                # Get the AIC code from the first result in the group
                aic_code = group_results[0]["AIC Code"]

                # Find and display safe alternatives
                safe_alternatives = find_safe_alternatives(
                    aic_code,
                    patient_icd_codes,
                    aic_name_map,
                    aic_icd_mapping,
                )

                if safe_alternatives:
                    alternative_text = (
                        "**Consider switching to a potentially safer drug:**\n"
                    )
                    for code, name, url in safe_alternatives:
                        if url:
                            alternative_text += f"- {code} - [{name}]({url})\n"
                        else:
                            alternative_text += f"- {code} - {name}\n"
                    st.info(alternative_text)
                else:
                    st.info("ℹ️ No safe alternative medications found in the database.")

                # Add a separator between different AIC-ICD combinations
                st.markdown("---")

        if not warning_found:
            # Get the URL for the selected drug from any warning entry
            drug_url = None
            for key, warnings in interaction_matrix.items():
                if key.startswith(selected_aic + "|"):
                    for warning in warnings:
                        if "aic_url" in warning:
                            drug_url = warning["aic_url"]
                            break
                    if drug_url:
                        break

            no_warning_text = """
                <div style='padding: 1rem; border-radius: 0.5rem; background-color: #f0f2f6; color: #31333F'>
                Based on the information of the drug leaflet and the condition(s), no contraindication has been found.
                """
            if drug_url:
                no_warning_text += f"""
                <br>
                <a href="{drug_url}" target="_blank" style="color: #31333F; text-decoration: underline;">View Leaflet</a>
                </div>
                """
            else:
                no_warning_text += "</div>"

            st.markdown(no_warning_text, unsafe_allow_html=True)

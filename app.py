import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime

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
st.sidebar.markdown(
    """
**Project Information** \n
This app checks for contraindications between existing diseases and drugs, that are prescibed by doctors. It was developed at Data Science Retreat.

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
    "Select Drug", options=[""] + aic_options, index=0, key="aic_selector"
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
                            (
                                name
                                for code, name, date, abatement in patient_icd_tuples
                                if code == icd
                            ),
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
                        (
                            name
                            for code, name, date, abatement in patient_icd_tuples
                            if code == icd
                        ),
                        "N/A",
                    ),
                    "Warning (Italian)": "Based on the information of the drug leaflet and the ICD description, no contraindication has been found.",
                    "AIC URL": "N/A",
                }
            )
    if results:
        st.subheader("Warnings")
        warning_found = False
        for idx, result in enumerate(results):
            if (
                result["Warning (Italian)"]
                != "Based on the information of the drug leaflet and the ICD description, no contraindication has been found."
            ):
                warning_found = True

                # Display warning in a container
                with st.container():
                    st.warning(
                        f"""
                        **AIC {result['AIC Code']} ({result['AIC Name']}) + ICD {result['ICD Code']} ({result['ICD Name']})**
                        
                        {result['Warning (Italian)']}
                        
                        [View AIC Details]({result['AIC URL']})
                        """
                    )

                    # Only show feedback buttons if feedback is enabled and feedback hasn't been given
                    # Create a unique key that includes the warning text
                    feedback_key = f"{result['AIC Code']}_{result['ICD Code']}_{hash(result['Warning (Italian)'])}"
                    if (
                        enable_feedback
                        and feedback_key not in st.session_state.feedback_given
                    ):
                        # Create unique keys for each warning's feedback buttons
                        accept_key = f"accept_{idx}"
                        reject_key = f"reject_{idx}"

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
        if not warning_found:
            st.markdown(
                """
                <div style='padding: 1rem; border-radius: 0.5rem; background-color: #f0f2f6; color: #31333F'>
                Based on the information of the drug leaflet and the ICD description, no contraindication has been found.
                </div>
                """,
                unsafe_allow_html=True,
            )

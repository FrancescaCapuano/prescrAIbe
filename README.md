<h1 align="center">Welcome to Prescr<span style='color: #FF8C00'>AI</span>be 💊</h1>
<p>
</p>

> This project is a prototype of an AI-powered clinical decision support tool designed to help healthcare providers prescribe medications more safely and efficiently. The system automatically analyzes a patient’s clinical history - using standards like ICD for diagnoses and FHIR for data integration - and checks for potential contraindications or risks based on official medication data from AIFA, the Italian Medicines Agency.


## Author

👤 **Francesca Capuano & Viktoria Leuschner**


## Overview
prescrAIbe is a prototype system designed to support safer and more informed medication prescriptions.

The system processes patient information (e.g. diagnoses and medical history) and checks for potential contraindications, risks, and inconsistencies based on structured medication data. It integrates medical standards such as ICD (diagnoses) and FHIR (health data representation).

The project combines data integration, rule-based checks, and AI-supported components within a unified pipeline.

## Project Structure
- `app.py` - main application entry point  
- `src/` - modular implementation of core functionality
- `scripts/` - higher-level scripts orchestrating processing steps and workflows
- `reports/eda/` - exploratory data analysis  
- `survey/` - evaluation materials  

## Notes
This repository represents a prototype developed in a collaborative setting.  
Some components are simplified and certain data sources are not included.
from langchain_core.prompts import PromptTemplate


def create_dynamic_prompt(drug_name, icd_code, icd_description):
    """Create a prompt template with variables already filled in"""

    formatted_template = f"""You are a medical assistant analyzing pharmaceutical documentation (e.g., drug leaflets).

Context:
{{context}}

Task:
Based only on the provided context, assess whether the drug "{drug_name}" has any undesired or harmful effects for patients with the condition identified by ICD code "{icd_code}", which refers to "{icd_description}".

Classify the interaction level according to the following scale:
- **Level 3 – Contraindicated**: The drug should not be used with this condition.
- **Level 2 – Use with Caution**: The drug may pose risks and should be used carefully or under monitoring.
- **Level 1 – No Known Issue**: The drug does not appear to have harmful effects for this condition in the provided context.
- **Level 0 – Insufficient Information**: The context does not provide enough data to assess the risk.

Then provide a short explanation based on the leaflet context, citing any specific warnings, contraindications, or adverse reactions.

Output format:
- **Risk Level**: [Level 0–3]
- **Justification**: [Explanation based on context]

Answer:
"""

    return PromptTemplate(
        template=formatted_template, input_variables=["context", "question"]
    )

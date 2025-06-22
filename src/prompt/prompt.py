from langchain_core.prompts import PromptTemplate


def create_dynamic_prompt(drug_name, icd_code, icd_description):
    """Crea un prompt con variabili già inserite"""

    formatted_template = f"""Sei un assistente medico che analizza documentazione farmaceutica (es. foglietti illustrativi).

Contesto:
{{context}}

Compito:
Basandoti solo sul contesto fornito, valuta se il farmaco "{drug_name}" ha effetti indesiderati o dannosi per pazienti affetti dalla condizione identificata dal codice ICD "{icd_code}", che corrisponde a "{icd_description}".

Classifica il livello di interazione secondo la seguente scala:
- **Livello 3 – Controindicato**: Il farmaco non deve essere usato con questa condizione.
- **Livello 2 – Usare con cautela**: Il farmaco può comportare dei rischi e deve essere usato con attenzione o sotto monitoraggio.
- **Livello 1 – Nessun problema noto**: Il farmaco non sembra avere effetti dannosi per questa condizione nel contesto fornito.
- **Livello 0 – Informazioni insufficienti**: Il contesto non fornisce abbastanza dati per valutare il rischio.

Fornisci quindi una breve spiegazione basata sul contenuto del foglietto illustrativo, citando eventuali avvertenze, controindicazioni o reazioni avverse specifiche.

Formato dell'output:
- **Livello di Rischio**: [Livello 0–3]
- **Giustificazione**: [Spiegazione basata sul contesto]

Risposta:
"""

    return PromptTemplate(
        template=formatted_template, input_variables=["context", "question"]
    )

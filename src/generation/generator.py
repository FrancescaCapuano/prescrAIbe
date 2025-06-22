from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain.chains import RetrievalQA


def get_llm(model_id: str = "gpt2"):
    """
    Loads and returns a HuggingFacePipeline LLM.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype="auto"
    )
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=512,
        temperature=0.7,
        top_p=0.95,
        repetition_penalty=1.15,
    )
    llm = HuggingFacePipeline(pipeline=pipe)
    return llm


def run_interaction_query(retriever, icd_code, drug_name, custom_rag_prompt):
    llm = get_llm()

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": custom_rag_prompt},
        return_source_documents=True,
    )

    result = qa_chain.invoke()

    print(result["source_documents"])
    return result["result"]


if __name__ == "__main__":
    llm = get_llm()

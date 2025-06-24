from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer  # , pipeline
from transformers.pipelines import pipeline
from langchain.chains import RetrievalQA
from langchain_community.llms import LlamaCpp
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from langchain_community.llms import LlamaCpp
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from huggingface_hub import hf_hub_download
from langchain.llms.base import LLM
from typing import Optional, List, Any
import logging


def get_llm(model_id: str = "gpt2"):
    """
    Loads and returns a HuggingFacePipeline LLM.
    """
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="auto", torch_dtype="auto"
    )
    pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)

    llm = HuggingFacePipeline(pipeline=pipe)
    return llm


class LlamaCppWrapper(LLM):
    """
    Wrapper to ensure LlamaCpp is properly recognized as a LangChain Runnable
    """

    def __init__(self, llama_cpp_instance):
        super().__init__()
        self.llama_cpp = llama_cpp_instance

    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Call the LlamaCpp model"""
        return self.llama_cpp._call(prompt, stop=stop, **kwargs)

    @property
    def _llm_type(self) -> str:
        """Return identifier of llm type"""
        return "llama_cpp_wrapper"

    def invoke(self, input_text: str, **kwargs) -> str:
        """Invoke method for compatibility"""
        return self._call(input_text, **kwargs)


def get_llm_gguf():
    """
    Loads and returns a LlamaCpp LLM for QuantFactory/Llama-3.2-1B-GGUF model.

    Returns:
        LlamaCpp LLM instance compatible with LangChain
    """
    llm = Llama(model_path="data/Llama-3.2-1B.Q2_K.gguf", n_ctx=2048, n_gpu_layers=20)

    """
    llm = Llama.from_pretrained(
        repo_id="data",
        filename="Llama-3.2-1B.Q2_K.gguf",
    )
    """

    # Return wrapped instance for better compatibility
    return LlamaCppWrapper(llm)


def run_interaction_query(
    retriever, icd_code, icd_description, drug_name, custom_rag_prompt
):
    llm = get_llm()

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": custom_rag_prompt},
        return_source_documents=True,
    )

    result = qa_chain.invoke(
        {
            "query": f"Quali effetti ha il farmaco {drug_name} sulla condizione {icd_description} (codice ICD: {icd_code})?"
        }
    )

    return result["result"]


if __name__ == "__main__":
    llm = get_llm()

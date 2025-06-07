import pymupdf4llm
import pdb

md_text = pymupdf4llm.to_markdown("data/raw/FI_001392_037600.pdf")
print(md_text)


# now work with the markdown text, e.g. store as a UTF8-encoded file
import pathlib

pathlib.Path("data/preprocessed/FI_001392_037600.md").write_bytes(md_text.encode())

"""
# As a first example for directly supporting LLM / RAG consumers, this version can output LlamaIndex documents:
md_read = pymupdf4llm.LlamaMarkdownReader()
data = md_read.load_data("input.pdf")
# The result 'data' is of type List[LlamaIndexDocument]
# Every list item contains metadata and the markdown text of 1 page.
#  A LlamaIndex document essentially corresponds to Python dictionary, where the markdown text of the page is one of the dictionary values. For instance the text of the first page is the the value of data[0].to_dict().["text"].
"""

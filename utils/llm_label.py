from langchain import hub
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.chat_models import ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s')

def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

def doc_labeller(file_path):
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    logging.debug(f"Data: {docs[0]}")
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs[:5])

    embeddings = OllamaEmbeddings(
        model="llama-7b",
    )
    
    vdb = FAISS.from_documents(splits, embeddings)
    
    retriever = vdb.as_retriever()
    # TODO: create my own prompt; thinking some structured output
    prompt = hub.pull("rlm/rag-prompt")
    logging.debug(f"Prompt: {prompt}")

    rag_chain = (
                {
                    "context": retriever | format_docs, 
                    "question": RunnablePassthrough()}
                | prompt
                | ChatOllama(
                    model = "llama3",
                    temperature = 0.8,
                    num_predict = 256,)
                | StrOutputParser()
            )
    
    label = rag_chain.invoke("Is this a quarterly report of an audited financial statement?")
    
    return label
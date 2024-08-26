import streamlit as st

from google.oauth2 import service_account

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_ollama import OllamaEmbeddings
# from langchain_ollama.chat_models import ChatOllama
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_google_vertexai import ChatVertexAI
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
# import json

from utils.prompt import chat_prompt

import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s')

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    logging.DEBUG("Found Google API Key" if GOOGLE_API_KEY!="" else "No Google API Key found")
except Exception as e:
    logging.error(f"Error loading Google API Key: {e}")

try:
    credentials = service_account.Credentials.from_service_account_info(
            st.secrets["vertex_ai_credentials"]
            )
    logging.debug("Credentials loaded successfully.")
except Exception as e:
    logging.error(f"Error loading credentials: {e}")

def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

def doc_labeller(file_path):
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    logging.debug(f"Data: {docs[0]}")
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs[:5])

    # embeddings = OllamaEmbeddings(
    #     model="llama3",
    # )
    
    embeddings = VertexAIEmbeddings(model_name="text-embedding-004", credentials=credentials)
    
    vdb = FAISS.from_documents(splits, embeddings)
    
    retriever = vdb.as_retriever()

    logging.debug(f"Prompt: {chat_prompt}")

    rag_chain = (
                {
                    "context": retriever | format_docs
                    }
                | chat_prompt
                | ChatVertexAI(
                    google_api_key=GOOGLE_API_KEY,
                    credentials=credentials)
                | StrOutputParser()
            )
    
    label = rag_chain.invoke("Is this an audited financial statement, and which company is it for?")
    
    # return json.loads(label)
    return label
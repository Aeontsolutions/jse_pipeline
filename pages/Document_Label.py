import os

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from utils.s3_operations import list_s3_files, download_pdf_from_s3
from langchain import hub
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.chat_models import ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    st.title("Label Documents")
    
    st.warning("Under construction!!!")
    
    # Initialize session state if not already set
    if 'tables_found' not in st.session_state:
        st.session_state['tables_found'] = None
        logging.debug("Initialized session state: tables_found is None.")

    if 'extracted_table' not in st.session_state:
        st.session_state['extracted_table'] = None
        logging.debug("Initialized session state: extracted_table is None.")

    files = list_s3_files()
    if files:
        selected_file_path = st.selectbox("Choose a file to label:", files)
        logging.debug(f"Selected file: {selected_file_path}")

        if st.button("Label"):
            temp_file_path = download_pdf_from_s3(selected_file_path)
            logging.debug(f"Downloaded file to: {temp_file_path}")
            pdf_viewer(temp_file_path, pages_to_render=[1, 2,3,4])
            
            loader = PyPDFLoader(temp_file_path)
            docs = loader.load()
            logging.debug(f"Data: {docs[0]}")
            
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs[:5])

            embeddings = OllamaEmbeddings(
                model="llama3",
            )
            
            vdb = FAISS.from_documents(splits, embeddings)
            
            retriever = vdb.as_retriever()
            prompt = hub.pull("rlm/rag-prompt")
            logging.debug(f"Prompt: {prompt}")


            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)


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

            st.write(rag_chain.invoke("Is this a quarterly report of an audited financial statement?"))
            
if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
            
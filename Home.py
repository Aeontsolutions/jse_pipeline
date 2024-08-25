import os

import streamlit as st

import logging

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    st.title("Financials Management App")
    
    st.write("""
             This app automatically labels a document and extracts tables from it.
             Visit the Document Label page to label a document and extract tables from it.
             Visit the Table Extraction page to extract tables from a document.
             Happy analysis!
             """)

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
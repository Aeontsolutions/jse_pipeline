import os

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from utils.s3_operations import list_s3_files, download_pdf_from_s3
from utils.textraction import extract_tables_from_document

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
            
            # DESIRED_PATTERNS = (r'table of contents', r'index')
            # st.session_state['tables_found'] = extract_tables_from_document(selected_file_path, DESIRED_PATTERNS)
            # logging.debug(f"Tables found: {st.session_state['tables_found']}")
            
            # if st.session_state['tables_found']:
            #     pages = [table.page for table in st.session_state['tables_found']]
            #     logging.debug(f"Pages to render: {pages}")
            #     pdf_viewer(temp_file_path, pages_to_render=pages)
            
if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
            
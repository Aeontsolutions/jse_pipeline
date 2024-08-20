import os

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from utils.s3_operations import list_s3_files, download_pdf_from_s3
from utils.textraction import extract_tables_from_document, get_table_by_page

import logging

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    st.title("Financials Extraction App")
    
    # st.write(
    #     "Has environment variables been set:",
    #     os.environ["AWS_ACCESS_KEY_ID"] == st.secrets["AWS_ACCESS_KEY_ID"],
    #     )
    
    # Initialize session state if not already set
    if 'tables_found' not in st.session_state:
        st.session_state['tables_found'] = None
        logging.debug("Initialized session state: tables_found is None.")

    if 'extracted_table' not in st.session_state:
        st.session_state['extracted_table'] = None
        logging.debug("Initialized session state: extracted_table is None.")
    
    # The sidebar
    # with st.sidebar:

    files = list_s3_files()
    # logging.debug(f"Files found: {files}")
    if files:

        selected_file_path = st.selectbox("Choose a file to extract tables from:", files)
        logging.debug(f"Selected file: {selected_file_path}")
            
        find_tables = st.button("Find Tables")
        if find_tables:
            temp_file_path = download_pdf_from_s3(selected_file_path)
            # logging.debug(f"Downloaded file to: {temp_file_path}")
                
            if not st.session_state['tables_found']:
                st.session_state['tables_found'] = extract_tables_from_document(f"s3://jse-bi-bucket/{selected_file_path}")
                logging.debug(f"Tables found: {st.session_state['tables_found']}")
                    
            # st.write("Number of tables found:", len(st.session_state['tables_found']))
            # st.write("Tables found:", st.session_state['tables_found'])
                                
            if st.session_state['tables_found']:
                pages = [table.page for table in st.session_state['tables_found']]
                logging.debug(f"Pages to render: {pages}")
                pdf_viewer(temp_file_path, pages_to_render=pages)
                    
    if st.session_state['tables_found']:
        page_num = st.selectbox("Choose a page to extract:", 
                            [table.page - 2 for table in st.session_state['tables_found']])
        logging.debug(f"Page number selected: {page_num}")
        
        if page_num is not None: 
            (table_title, selected_table) = get_table_by_page(st.session_state['tables_found'], page_num + 2)
            # logging.debug(f"Selected table: {selected_table}")
            st.write("Table title:", table_title)
            st.dataframe(selected_table)
            
            st.download_button(
                label="Download selected table",
                data=selected_table.to_csv(index=False),
                file_name=f'{table_title.lower().replace(" ", "_")}.csv',
                mime="text/csv",
            )

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
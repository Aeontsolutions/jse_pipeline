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
                            [table.page for table in st.session_state['tables_found']])
        logging.debug(f"Page number selected: {page_num}")
        
        if page_num is not None: 
            selected_table = get_table_by_page(st.session_state['tables_found'], page_num)
            # logging.debug(f"Selected table: {selected_table}")
            st.dataframe(selected_table)
            selected_table.to_csv("selected_table.csv", index=False)
            
            # extracted_table = selected_table.to_pandas(use_columns=True)
            # st.write("Extracted table:", extracted_table)
            # st.table(extracted_table)
    #         for table in tables_found:
    #             if st.button(f"Textract {table.title.text}"):
    #                 st.write(f'Table title: {table.title.text}, page number: {table.page}')
    #                 extracted_table = table.to_pandas(use_columns=True)
    #     else:
    #         st.write("No tables found.")
            
    # if extracted_table is not None:
    #     st.dataframe(extracted_table)
    # else:
    #     st.write("No table found.")
        
        #         tables_found = extract_tables_from_document(f"s3://jse-bi-bucket/{selected_file_path}")
        #         if tables_found:
        #             st.write(f"{len(tables_found)} tables found!")
        #             # Create a column on the right
        #             col1, col2 = st.columns(2)  # Adjust ratios as needed
                    
        #             with col1:  # Show tables in the left column
        #                 for table in tables_found:
        #                     st.write(f'Table title: {table.title.text}, page number: {table.page}')

        #             with col2:  # Show images in the right column  
        #                 page_num = st.number_input("Enter the page number of the table you're interested in:", min_value=1, step=1)
        #                 if page_num > 0 and page_num <= len(tables_found):
        #                     selected_table = get_table_by_page(tables_found, page_num)
                            
        #                     extracted_table = selected_table.to_pandas(use_columns=True)
                    
        #                     st.dataframe(extracted_table.head())
                          
        #                 else:
        #                     st.write(f"No table found on page {page_num}.")
                    
                    
        #         else:
        #             st.write("No tables matching the desired patterns were found.")
        # else:
        #     st.write("No files found.")

    # elif operation == "Select file":
    #     if st.button("Show files"):
    #         files = select_file_from_s3(bucket_name, "")
    #         # Instead of printing to console, show the files in Streamlit
    #         if files:
    #             selected_file = st.selectbox("Choose a file:", files)
    #             # Here you can decide what action to take after selecting the file, e.g., display its content or metadata.

    # elif operation == "Upload file":
    #     uploaded_file = st.file_uploader("Choose a file")
    #     if uploaded_file:
    #         s3_file_name = st.text_input("Enter desired S3 file name or leave blank:")
    #         if st.button("Upload"):
    #             # Assuming `upload_file_to_s3` returns a response or message
    #             response = upload_file_to_s3(uploaded_file, bucket_name, s3_file_name or uploaded_file.name)
    #             st.write(response)

    # elif operation == "Delete file":
    #     file_to_delete = st.text_input("Enter the name of the file to delete:")
    #     if st.button("Delete"):
    #         # Assuming `delete_file_from_s3` returns a response or message
    #         response = delete_file_from_s3(bucket_name, file_to_delete)
    #         st.write(response)
            
    # if operation == "Textract Tables":
    #     selected_file_path = st.text_input("Enter the S3 file path:")
    #     if st.button("Extract Tables"):
    #         tables_found = extract_tables_from_document(selected_file_path)
    #         if tables_found:
    #             st.write(f"{len(tables_found)} tables found!")
    #             page_num = st.number_input("Enter the page number of the table you're interested in:", min_value=1, step=1)
    #             selected_table = get_table_by_page(tables_found, page_num)
    #             if selected_table:
    #                 st.write(f'Selected table title: {selected_table.title.text}, page number: {selected_table.page}')
    #             else:
    #                 st.write(f"No table found on page {page_num}.")
    #         else:
    #             st.write("No tables matching the desired patterns were found.")

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
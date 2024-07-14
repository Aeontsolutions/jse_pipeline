import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from utils.s3_operations import list_s3_files, download_pdf_from_s3
from utils.textraction import extract_tables_from_document, get_table_by_page
import os
from dotenv import load_dotenv

def main():
    st.title("Financials Extraction App")

    # Dropdown menu for user to select an action
    operation = st.selectbox(
        "Choose an operation:",
        [
            "List files", 
            # "Select file",
            # "Textract tables", 
            # "Upload file", 
            # "Delete file"
            ]
    )

    if operation == "List files":
        files = list_s3_files()
        if files:
            st.write("Files in bucket:")
            selected_file_path = st.selectbox("Choose a file to extract tables from:", files)
            
            if st.button("Extract Tables"):
                temp_file_path = download_pdf_from_s3(selected_file_path)
                tables_found = extract_tables_from_document(f"s3://jse-bi-bucket/{selected_file_path}")
                            
                col1, col2 = st.columns(2)
                with col1:
                    if tables_found:
                        pdf_viewer(temp_file_path, pages_to_render=[table.page for table in tables_found])
                    
                with col2:
                    st.write("Extracted Table:")                    
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
            
    if operation == "Textract Tables":
        selected_file_path = st.text_input("Enter the S3 file path:")
        if st.button("Extract Tables"):
            tables_found = extract_tables_from_document(selected_file_path)
            if tables_found:
                st.write(f"{len(tables_found)} tables found!")
                page_num = st.number_input("Enter the page number of the table you're interested in:", min_value=1, step=1)
                selected_table = get_table_by_page(tables_found, page_num)
                if selected_table:
                    st.write(f'Selected table title: {selected_table.title.text}, page number: {selected_table.page}')
                else:
                    st.write(f"No table found on page {page_num}.")
            else:
                st.write("No tables matching the desired patterns were found.")

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
import pandas as pd
import requests
import tempfile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def update_google_sheet(url, proposed_name):
    creds = Credentials(
        None,
        refresh_token=st.secrets["google_credentials"]["refresh_token"],
        token_uri=st.secrets["google_credentials"]["token_uri"],
        client_id=st.secrets["google_credentials"]["client_id"],
        client_secret=st.secrets["google_credentials"]["client_secret"]
    )
    service = build('sheets', 'v4', credentials=creds)
    
    # Append to Google Sheet
    sheet_id = st.secrets["google_sheet_id"]
    range_name = 'Sheet2!A:B'  # Just URL and name
    values = [[url, proposed_name]]
    body = {'values': values}
    
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()

def download_pdf_from_url(url):
    response = requests.get(url)
    if response.status_code == 200:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(response.content)
            return tmp_file.name
    return None

def get_reviewed_urls():
    try:
        creds = Credentials(
            None,
            refresh_token=st.secrets["google_credentials"]["refresh_token"],
            token_uri=st.secrets["google_credentials"]["token_uri"],
            client_id=st.secrets["google_credentials"]["client_id"],
            client_secret=st.secrets["google_credentials"]["client_secret"]
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get all reviewed URLs from Google Sheet
        sheet_id = st.secrets["google_sheet_id"]
        range_name = 'Sheet2!A:A'  # First column contains URLs
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        # Extract URLs from the result, skip header row
        values = result.get('values', [])[1:]  # Skip header row
        return {row[0] for row in values}  # Convert to set for faster lookup
    except Exception as e:
        logging.error(f"Error getting reviewed URLs: {str(e)}")
        return set()

def main():
    st.title("PDF Name Validator")
    
    # Initialize session state for tracking progress
    if 'current_index' not in st.session_state:
        st.session_state['current_index'] = 0
    
    # Load CSV file and get reviewed URLs
    try:
        df = pd.read_csv(st.secrets["CSV_PATH"])
        reviewed_urls = get_reviewed_urls()
        
        # Filter out already reviewed documents
        df = df[~df['old_guid'].isin(reviewed_urls)].reset_index(drop=True)
        
        if len(df) == 0:
            st.success("All PDFs have been reviewed!")
            return
            
        if st.session_state['current_index'] < len(df):
            current_row = df.iloc[st.session_state['current_index']]
            
            # Display PDF
            pdf_url = current_row['old_guid']
            initial_proposed_name = current_row['new_post_name']
            
            temp_file_path = download_pdf_from_url(pdf_url)
            if temp_file_path:
                st.write("### Proposed new name:")
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Add text input for editing the proposed name
                    proposed_name = st.text_input("Edit name if needed:", 
                                            value=initial_proposed_name,
                                            key=f"name_input_{st.session_state['current_index']}")
                    
                with col2:
                    if st.button("Approve", use_container_width=True):
                        update_google_sheet(pdf_url, proposed_name)
                        st.session_state['current_index'] += 1
                        st.rerun()
                
                st.write("")

            else:
                st.error("Failed to download PDF")
            
            # Display PDF viewer
            pdf_viewer(temp_file_path, pages_to_render=[1, 2, 3, 4], height=800)
            
        else:
            st.success("All PDFs have been reviewed!")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
            
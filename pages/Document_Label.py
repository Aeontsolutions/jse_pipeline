import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
import pandas as pd
import requests
import tempfile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_available_sheets():
    try:
        creds = Credentials(
            None,
            refresh_token=st.secrets["google_credentials"]["refresh_token"],
            token_uri=st.secrets["google_credentials"]["token_uri"],
            client_id=st.secrets["google_credentials"]["client_id"],
            client_secret=st.secrets["google_credentials"]["client_secret"]
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get spreadsheet metadata
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=st.secrets["google_sheet_id"]
        ).execute()
        
        # Extract sheet names
        sheets = sheet_metadata.get('sheets', [])
        sheet_names = [sheet['properties']['title'] for sheet in sheets]
        
        return sheet_names
    except Exception as e:
        logging.error(f"Error getting sheet names: {str(e)}")
        return []

def download_pdf_from_guid(guid):
    try:
        # Remove '@' from the start of the URL if present
        url = guid.lstrip('@') if guid.startswith('@') else guid
        
        response = requests.get(url)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(response.content)
                return tmp_file.name
        else:
            logging.error(f"Failed to download PDF from URL {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error downloading PDF from URL {url}: {str(e)}")
        return None

def update_google_sheet(row_number, selected_sheet, new_post_name, action):
    try:
        logging.info(f"Attempting to update sheet: {selected_sheet}, row: {row_number}, new name: {new_post_name}, action: {action}")
        
        creds = Credentials(
            None,
            refresh_token=st.secrets["google_credentials"]["refresh_token"],
            token_uri=st.secrets["google_credentials"]["token_uri"],
            client_id=st.secrets["google_credentials"]["client_id"],
            client_secret=st.secrets["google_credentials"]["client_secret"]
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Update both the new_post_name and verified columns
        update_range = f"'{selected_sheet}'!D{row_number}:E{row_number}"
        update_body = {
            'values': [[new_post_name, action]]
        }
        
        logging.info(f"Updating range: {update_range}")
        logging.info(f"Update body: {update_body}")
        
        result = service.spreadsheets().values().update(
            spreadsheetId=st.secrets["google_sheet_id"],
            range=update_range,
            valueInputOption='RAW',
            body=update_body
        ).execute()
        
        logging.info(f"Update result: {result}")
        st.success("Successfully updated the sheet!")
            
    except Exception as e:
        st.error(f"Error updating sheet: {str(e)}")
        logging.error(f"Error updating sheet: {str(e)}")
        # Print full exception details
        import traceback
        logging.error(traceback.format_exc())

def get_sheet_data(selected_sheet):
    try:
        creds = Credentials(
            None,
            refresh_token=st.secrets["google_credentials"]["refresh_token"],
            token_uri=st.secrets["google_credentials"]["token_uri"],
            client_id=st.secrets["google_credentials"]["client_id"],
            client_secret=st.secrets["google_credentials"]["client_secret"]
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get all data from the selected sheet
        range_name = f"'{selected_sheet}'!A:E"  # Adjust range based on your columns
        result = service.spreadsheets().values().get(
            spreadsheetId=st.secrets["google_sheet_id"],
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
            
        # Convert to DataFrame
        df = pd.DataFrame(values[1:], columns=values[0])  # First row as headers
        
        # Add row numbers before filtering
        df['sheet_row'] = range(2, len(df) + 2)  # +2 because sheet is 1-indexed and we skipped header
        
        # Filter rows where verified is not equal to yes
        df = df[df['verified'].fillna('no') != 'yes'].reset_index(drop=True)
        
        logging.info(f"Found {len(df)} unverified documents")
        return df
        
    except Exception as e:
        logging.error(f"Error getting sheet data: {str(e)}")
        return pd.DataFrame()

def main():
    st.title("PDF Name Validator")
    
    # Get available sheets and let user select one
    sheet_names = get_available_sheets()
    if not sheet_names:
        st.error("No sheets found or error accessing Google Sheets")
        return
        
    selected_sheet = st.selectbox(
        "Select sheet to work with:",
        options=sheet_names,
        key="sheet_selector"
    )
    
    # Initialize current_row_number in session state if it doesn't exist
    if 'current_row_number' not in st.session_state:
        st.session_state['current_row_number'] = 0
    
    # Load data from selected sheet instead of CSV
    try:
        df = get_sheet_data(selected_sheet)
        
        # number of outstanding documents
        outstanding_documents = len(df)
        st.metric("Outstanding documents", outstanding_documents)
        
        if df.empty:
            st.success("All documents have been verified!")
            return
        
        # Make sure current_row_number doesn't exceed the dataframe length
        if st.session_state['current_row_number'] >= len(df):
            st.session_state['current_row_number'] = 0
            
        # Display current unreviewed document
        current_row = df.iloc[st.session_state['current_row_number']]
        sheet_row_number = current_row['sheet_row']
        
        temp_file_path = download_pdf_from_guid(current_row['guid'])
        if temp_file_path:
            st.write(f"### Post Date: {current_row['post_date']}")
            col1, col2 = st.columns([3, 1]) 
            with col1:
                st.info(f"### Is this a {selected_sheet}?")
                st.write("### Proposed new name:")
                proposed_name = st.text_input("Edit name if needed:", 
                                            value=current_row['new_post_name'])
            with col2:
                if st.button("Verify", use_container_width=True):
                    logging.info(f"Verify button clicked. Row: {sheet_row_number}, Sheet: {selected_sheet}, Name: {proposed_name}")
                    update_google_sheet(sheet_row_number, selected_sheet, proposed_name, 'yes')
                    st.rerun()
                if st.button("Skip", use_container_width=True):
                    logging.info(f"Skip button clicked. Row: {sheet_row_number}, Sheet: {selected_sheet}")
                    update_google_sheet(sheet_row_number, selected_sheet, proposed_name, 'skipped')
                    st.session_state['current_row_number'] += 1
                    st.rerun()
            
            pdf_viewer(temp_file_path, pages_to_render=[1, 2, 3, 4], height=800)
            
            st.write("")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
            
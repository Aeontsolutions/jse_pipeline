import streamlit as st
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
        logging.error(f"Error getting available sheets: {e}")
        return []

def get_sheet_data(sheet_name):
    try:
        creds = Credentials(
            None,
            refresh_token=st.secrets["google_credentials"]["refresh_token"],    
            token_uri=st.secrets["google_credentials"]["token_uri"],
            client_id=st.secrets["google_credentials"]["client_id"],
            client_secret=st.secrets["google_credentials"]["client_secret"]
        )
        
        service = build('sheets', 'v4', credentials=creds)
        
        # Get data from sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=st.secrets["google_sheet_id"],
            range=sheet_name
        ).execute()
        
        # Convert to DataFrame
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
            
        # Create DataFrame directly from all values
        df = pd.DataFrame(values)
        
        # Use first row as headers
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df
    except Exception as e:
        logging.error(f"Error getting sheet data: {e}")
        return pd.DataFrame()

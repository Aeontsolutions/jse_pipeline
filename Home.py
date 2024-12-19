import os

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import pandas as pd

import logging

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    
def get_available_sheets():
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri=os.getenv("GOOGLE_TOKEN_URI"),
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get spreadsheet metadata
        sheet_metadata = service.spreadsheets().get(
            spreadsheetId=os.getenv("GOOGLE_SHEET_ID")
        ).execute()
        
        # Extract sheet names
        sheets = sheet_metadata.get('sheets', [])
        sheet_names = [sheet['properties']['title'] for sheet in sheets]
        
        return sheet_names
    except Exception as e:
        print(f"Error getting sheet names: {str(e)}")
        return []
    
available_sheets = get_available_sheets()

def get_sheet_data(sheet_name):
    """Get data from a specific sheet"""
    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            token_uri=os.getenv("GOOGLE_TOKEN_URI"),
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Get data from sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=os.getenv("GOOGLE_SHEET_ID"),
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
        print(f"Error getting data from sheet {sheet_name}: {str(e)}")
        return pd.DataFrame()

# Get all sheet data and concatenate
all_data = []
for sheet_name in available_sheets:
    print(f"Processing sheet: {sheet_name}")
    sheet_df = get_sheet_data(sheet_name)
    if not sheet_df.empty:
        sheet_df['source_sheet'] = sheet_name  # Add source sheet name as column
        # print(len(sheet_df[sheet_df["verified"] != "yes"]))
        all_data.append(sheet_df)

# Concatenate all dataframes
final_df = pd.concat(all_data, ignore_index=True)
total_rows = len(final_df)

# Drop rows where "verified" is not "yes"
final_df = final_df[final_df["verified"] == "yes"]
# drop duplicates
final_df = final_df.drop_duplicates(subset=["guid"])
verified_rows = len(final_df)

def main():
    st.title("Financials Management App")
    
    st.write("""
             This app assists with the labeling and extraction of financial documents.
             Visit the Document Label page to label a document and extract tables from it.
             Visit the Table Extraction page to extract tables from a document.
             Happy analysis!
             """)
    st.header("Progress Report")
    st.write("""
             This is the progress of the document labeling and table extraction process.
             """)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Total rows", total_rows)
    col2.metric(f"Percent of master sheet", round(total_rows / 6676, 2))
    col3.metric(f"Number of verified", verified_rows)
    col4.metric(f"Percent of master sheet verified", round(verified_rows / 6676, 2))

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
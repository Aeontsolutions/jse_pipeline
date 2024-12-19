import os

import streamlit as st
from utils.gsheet_operations import get_available_sheets, get_sheet_data
import pandas as pd

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    with st.spinner("Measuring progress..."):
        
        available_sheets = get_available_sheets()
        all_data = pd.concat([get_sheet_data(sheet) for sheet in available_sheets], ignore_index=True)
        
        total_rows = len(all_data)

        # Drop rows where "verified" is not "yes"
        all_data = all_data[all_data["verified"] == "yes"]
        # drop duplicates
        all_data = all_data.drop_duplicates(subset=["guid"])
        verified_rows = len(all_data)
        
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Total rows", total_rows)
    col2.metric(f"Percent of master sheet", f"{round(total_rows / 6676, 2)}%")
    col3.metric(f"Number of verified", verified_rows)
    col4.metric(f"Percent of verified", f"{round(verified_rows / total_rows, 2)}%")

if __name__ == "__main__":
    main()
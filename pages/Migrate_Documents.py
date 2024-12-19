import streamlit as st
import pandas as pd
from utils.gsheet_operations import get_available_sheets, get_sheet_data

import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

st.title("Migrate Documents")
st.write("""
         This page is used to migrate documents to the S3 bucket.
         """)

with st.spinner("Loading data..."):
    available_sheets = get_available_sheets()
    all_data = pd.concat([get_sheet_data(sheet).assign(sheet_name=sheet) for sheet in available_sheets], ignore_index=True)
    all_data = all_data[all_data["verified"] == "yes"]
    origin = pd.read_csv("pages/file_listing_with_guids.csv")

st.dataframe(all_data)
st.dataframe(origin)

st.radio("Migrate Documents", 
         options=["Migrate to ATS", "Migrate to JSE"], 
         index=0, 
         horizontal=True)

st.button("Migrate Documents")
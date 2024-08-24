import os

import streamlit as st
from pages import textraction_page

import logging

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    st.title("Financials Extraction App")
    
    # The sidebar
    page = st.sidebar.selectbox("Choose an option:", ["Extract", "Label"])
    
    if page == "Extract":
        textraction_page.main()
    elif page == "Label":
        st.write("Coming soon...")

if __name__ == "__main__":
    
    load_dotenv()

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    main()
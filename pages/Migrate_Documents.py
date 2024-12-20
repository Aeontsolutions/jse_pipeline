import streamlit as st
import pandas as pd
from utils.gsheet_operations import get_available_sheets, get_sheet_data
import boto3
import logging
import tempfile
import botocore
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_data_for_migration():
    available_sheets = get_available_sheets()
    all_data = pd.concat([get_sheet_data(sheet).assign(sheet_name=sheet) for sheet in available_sheets], ignore_index=True)
    all_data = all_data[all_data["verified"] == "yes"]
    origin = pd.read_csv("file_listing.csv")
    merged_data = all_data.merge(origin, on=["guid", "post_name", "post_date"], how="inner")
    return merged_data

def migrate_documents(destination, data):
    try:    
        source_client = boto3.client(
            's3', 
            region_name='us-east-1',
            aws_access_key_id=st.secrets.JSE_ACCESS_KEY_ID,
            aws_secret_access_key=st.secrets.JSE_SECRET_ACCESS_KEY
        )

    except Exception as e:
        logging.error(f"Error creating source client: {e}")
        return
    
    if destination == "Migrate to ATS":
        try:
            destination_client = boto3.client(
                's3', 
                region_name='us-east-1',
                aws_access_key_id=st.secrets.ATS_ACCESS_KEY_ID,
                aws_secret_access_key=st.secrets.ATS_SECRET_ACCESS_KEY
            )
        except Exception as e:
            logging.error(f"Error creating destination client: {e}")
            return
        
    else:
        destination_client = source_client
    
    try:
        for index, row in data.iterrows():
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                source_client.download_file(st.secrets.JSE_BUCKET_NAME, row['origin_file_loc'], temp_file.name)
                destination_client.upload_file(temp_file.name, st.secrets.ATS_TARGET_BUCKET, row['destination_file_loc'])
    except Exception as e:
        logging.error(f"Error downloading or uploading files: {e}")
        return
    
    st.success("Documents migrated successfully")
    
st.title("Migrate Documents")
st.write("""
         This page is used to migrate documents to the S3 bucket.
         """)

col1, col2 = st.columns(2)
with col1:
    area_to_migrate = st.radio("Migrate Documents", 
             options=["Migrate to ATS"], 
             index=0, 
             horizontal=True)
    
    with st.spinner("Loading data..."):
        merged_data = get_data_for_migration()
        
    # create a new column called "doc_type"
    merged_data["doc_type"] = merged_data["new_post_name"].apply(lambda x: "bulletin" if x.split("-")[0].lower() == "jse_weekly_bulletin" else x.split("-")[2].lower())

    # get the post_year and post_month from the post_date column
    merged_data["post_year"] = pd.to_datetime(merged_data["post_date"]).dt.year
    merged_data["post_month"] = pd.to_datetime(merged_data["post_date"]).dt.month

    # lower the InstrumentName column and replace spaces with underscores
    merged_data["InstrumentName"] = merged_data["InstrumentName"].str.lower().str.replace(" ", "_")

    # create the origin_file_name column
    merged_data["origin_file_loc"] = merged_data["guid"].str.replace(
        "https://www.jamstockex.com/wp-content/uploads/", 
        "all-files/"
    )

    if area_to_migrate == "Migrate to ATS":
        destination_fldr = "organized/"
        # create a new column called "destination_file_loc" 
        merged_data["destination_file_loc"] = destination_fldr + merged_data["InstrumentName"] + "/" + merged_data["doc_type"] + "/" + merged_data["post_year"].astype(str) + "/" + merged_data["post_month"].astype(str) + "/" + merged_data["new_post_name"]
    else:
        destination_fldr = "organized/"
        merged_data["destination_file_loc"] = destination_fldr + merged_data["InstrumentName"] + "/" + merged_data["doc_type"] + "/" + merged_data["post_year"].astype(str) + "/" + merged_data["post_month"].astype(str) + "/" + merged_data["new_post_name"]
        

with st.expander("Data Preview"):
    merged_data = merged_data[["guid", "origin_file_loc", "post_date", "doc_type", "destination_file_loc"]]
    st.dataframe(merged_data)
    
with col2:
    if st.button("Migrate Documents"):
        warning = st.warning("⚠️ Please do not close this tab while migration is in progress...", icon="⚠️")
        
        # Create a progress bar
        progress_bar = st.progress(0)
        total_files = len(merged_data)
        
        # Create a status message
        status_text = st.empty()
        
        # Wrap the migration in a try-finally to ensure we clean up the warning
        try:
            for index, row in enumerate(merged_data.iterrows()):
                # Update status message
                status_text.text(f"Migrating file {index + 1} of {total_files}: {row[1]['origin_file_loc']}")
                
                # Update progress bar
                progress_bar.progress((index + 1) / total_files)
                
                # Your existing migration code here
                migrate_documents(area_to_migrate, pd.DataFrame([row[1]]))
                
            # Success message
            warning.success("✅ Migration completed successfully! You can now close this tab.")
            
        except Exception as e:
            # Error message
            warning.error(f"❌ An error occurred during migration: {str(e)}")
            
        finally:
            # Clean up the status message
            status_text.empty()
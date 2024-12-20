import streamlit as st
import pandas as pd
from utils.gsheet_operations import get_available_sheets, get_sheet_data
import boto3
import logging
import tempfile
import concurrent.futures
import os
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_data_for_migration():
    available_sheets = get_available_sheets()
    all_data = pd.concat([get_sheet_data(sheet).assign(sheet_name=sheet) for sheet in available_sheets], ignore_index=True)
    all_data = all_data[all_data["verified"] == "yes"]
    origin = pd.read_csv("file_listing.csv")
    merged_data = all_data.merge(origin, on=["guid", "post_name", "post_date"], how="inner")
    return merged_data

def migrate_documents_batch(destination, data_batch):
    """
    Migrate a batch of documents from source to destination S3 bucket.
    Args:
        destination (str): Destination identifier (e.g., "ATS")
        data_batch (pd.DataFrame): DataFrame containing batch of migration data
    """
    try:    
        source_client = boto3.client(
            's3', 
            region_name='us-east-1',
            aws_access_key_id=st.secrets.JSE_ACCESS_KEY_ID,
            aws_secret_access_key=st.secrets.JSE_SECRET_ACCESS_KEY
        )
    except Exception as e:
        logging.error(f"Error creating source client: {e}")
        raise e
    
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
            raise e
    else:
        destination_client = source_client
    
    results = []
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_file = {}
        
        for _, row in data_batch.iterrows():
            future = executor.submit(
                transfer_single_file,
                source_client,
                destination_client,
                row['origin_file_loc'],
                row['destination_file_loc'],
                st.secrets.JSE_BUCKET_NAME,
                st.secrets.ATS_TARGET_BUCKET
            )
            future_to_file[future] = row['origin_file_loc']
        
        for future in concurrent.futures.as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                future.result()
                results.append((file_path, True, None))
            except Exception as e:
                results.append((file_path, False, str(e)))
    
    return results

def transfer_single_file(source_client, dest_client, source_path, dest_path, source_bucket, dest_bucket):
    """Helper function to transfer a single file"""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        try:
            source_client.download_file(source_bucket, source_path, temp_file.name)
            dest_client.upload_file(temp_file.name, dest_bucket, dest_path)
        finally:
            os.unlink(temp_file.name)  # Clean up temp file

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
        
        # Keep track of successful and failed migrations
        success_count = 0
        failed_files = []
        
        try:
            # Process in batches of 50 files
            BATCH_SIZE = 50
            for batch_start in range(0, len(merged_data), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(merged_data))
                current_batch = merged_data.iloc[batch_start:batch_end]
                
                # Update status message
                status_text.text(f"Migrating batch {batch_start//BATCH_SIZE + 1} of {(len(merged_data)-1)//BATCH_SIZE + 1}")
                
                # Process the batch
                results = migrate_documents_batch(area_to_migrate, current_batch)
                
                # Process results
                for file_path, success, error in results:
                    if success:
                        success_count += 1
                    else:
                        failed_files.append((file_path, error))
                
                # Update progress bar
                progress_bar.progress(batch_end / total_files)
            
            # Final status message
            if len(failed_files) == 0:
                warning.success(f"✅ Migration completed successfully! {success_count} files migrated.")
            else:
                warning.warning(f"⚠️ Migration completed with some issues.\n"
                              f"Successfully migrated: {success_count} files\n"
                              f"Failed: {len(failed_files)} files")
                # Show failed files in an expander
                with st.expander("Show failed files"):
                    for file, error in failed_files:
                        st.error(f"{file}: {error}")
            
        except Exception as e:
            warning.error(f"❌ Batch processing error: {str(e)}")
        
        finally:
            # Clean up the status message
            status_text.empty()
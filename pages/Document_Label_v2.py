import os
import boto3
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import io
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
import logging
import dotenv
import base64
import re
import csv
import time
from datetime import datetime

# Add this before loading environment variables
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_ENDPOINT"] = ""  # Disable endpoint
os.environ["LANGCHAIN_API_KEY"] = ""   # Clear API key

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("JSE_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("JSE_SECRET_ACCESS_KEY")
)

def list_s3_files():
    """
    List all files in the specified S3 bucket.

    Parameters:
    - bucket_name (str): Name of the S3 bucket.

    Returns:
    - List of file names in the bucket.
    """
    files = []

    bucket_name = os.getenv("S3_BUCKET_NAME")
    prefix = os.getenv("S3_PREFIX")
    extension = ".pdf"  # Hardcoding to only search for PDFs

    # List objects within the specified bucket with the specified prefix
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
    
    logger.info(f"Listing files in {bucket_name} with prefix {prefix}")

    for page in pages:
        for obj in page.get('Contents', []):
            if obj['Key'].endswith(extension):
                files.append(obj['Key'])

    return files

def extract_pages(file_path, num_pages=3):
    """
    Extract the first n pages of a PDF and convert them to image binaries
    Args:
        file_path: S3 key path to the PDF file
        num_pages: Number of pages to extract (default: 3)
    Returns:
        List of image binaries (bytes objects)
    """
    # Create a temporary file to store the downloaded PDF
    temp_file = '/tmp/temp.pdf'
    bucket_name = os.getenv("S3_BUCKET_NAME")
    
    try:
        # Download the file from S3
        logger.info(f"Downloading {file_path} from S3")
        s3.download_file(bucket_name, file_path, temp_file)
        
        # Process the downloaded file
        logger.info(f"Processing downloaded file")
        pdf = PdfReader(temp_file)
        total_pages = len(pdf.pages)
        
        # Adjust num_pages if it exceeds total pages
        num_pages = min(num_pages, total_pages)
        
        # Convert PDF pages to images
        logger.info(f"Converting {num_pages} pages to images")
        images = convert_from_path(temp_file, first_page=num_pages, last_page=num_pages)
        
        # Convert images to binary format
        logger.info(f"Converting {num_pages} images to binary format")
        image_binaries = []
        for image in images:
            with io.BytesIO() as img_byte_arr:
                image.save(img_byte_arr, format='PNG')
                image_binaries.append(img_byte_arr.getvalue())
        
        return image_binaries
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)

def get_candidate_labels(img_binary: bytes):
    """
    Label a document image
    Args:
        img_binary: Image binary
    Returns:
        Labeled document
    """
    img_base64 = base64.b64encode(img_binary).decode('utf-8')
    
    model = ChatVertexAI(
        model="gemini-1.5-flash-001",
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    data_url = f"data:image/png;base64,{img_base64}"
    
    LABEL_PROMPT = """Which ONE of the following documents is this?

    - JSE Weekly Bulletin 
    - JSE Monthly Regulatory Report
    - Company Acquistion Notices
    - APO/IPO Prospectus
    - Prospectus
    - Notice of: Appointment Letters/Change in Managers/Disposal/Resignation/Trading in Shares
    - Notice of Dividend: Consideration/Declaration
    - Circular Letter to Shareholders
    - Annual Meeting Documents 2024:
      * Notice with Pre-registration Guidelines
      * Management Proxy Circular
      * Form of Proxy
    - Notice of and Updates On Mergers
    - NAV Reports: Daily/Unaudited
    - Financial Statements:
      * Annual Audited
      * Quarterly (Q1-Q4)
    - Special Circulars:
      * Directors'
      * Rights Issue
      * Take Over Bid

    Provide the document type and company name in the following markdown JSON format, without any JSON formatting characters:
    ```{
        "document_type": "<exact match from list above>",
        "company_name": "<extracted company name>"
    }```

    If type cannot be determined, return:
    ```{
        "document_type": "Unknown",
        "company_name": "<extracted company name>"
    }```"""
    
    message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": LABEL_PROMPT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ]
            )
    
    chain = model | JsonOutputParser()
    
    max_retries = 3  # Define the maximum number of retries
    retry_count = 0  # Initialize retry counter

    while retry_count < max_retries:
        try:
            logger.info(f"Invoking model for the {retry_count + 1} time")
            response = chain.invoke([message])

            if isinstance(response, str):
                response = response.replace('```json', '').replace('```', '').strip()
            if "document_type" in response and "company_name" in response:
                logger.info(f"Received evaluation: {response}")
                return response
            else:
                logger.warning(f"Response missing 'document_type' or 'company_name': {response}")
                retry_count += 1
        except Exception as e:
            logger.error(f"Error during invocation or processing: {str(e)}")
            retry_count += 1

    if retry_count == max_retries:
        logger.error("Failed to receive a valid response after 3 attempts. Please try again later.")
        raise RuntimeError("Failed to receive a valid response after 3 attempts. Please try again later.")
    
def label_document(candidate_labels: list):
    model = ChatVertexAI(
        model="gemini-1.5-flash-001",
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    
    LABEL_PROMPT = """Given this list of potential document types, identify what the document most likely is. ONLY choose from the following list:
    
    - JSE Weekly Bulletin 
    - JSE Monthly Regulatory Report
    - Company Acquistion Notices
    - APO/IPO Prospectus
    - Prospectus
    - Notice of: Appointment Letters/Change in Managers/Disposal/Resignation/Trading in Shares
    - Notice of Dividend: Consideration/Declaration
    - Circular Letter to Shareholders
    - Annual Meeting Documents 2024:
      * Notice with Pre-registration Guidelines
      * Management Proxy Circular
      * Form of Proxy
    - Notice of and Updates On Mergers
    - NAV Reports: Daily/Unaudited
    - Financial Statements:
      * Annual Audited
      * Quarterly (Q1-Q4)
    - Special Circulars:
      * Directors'
      * Rights Issue
      * Take Over Bid

    Provide the document type and company name in the following markdown JSONformat, without any JSON formatting characters:
    ```{
        "document_type": "<exact match from list above>",
        "company_name": "<extracted company name>"
    }

    If type cannot be determined, return:
    ```{
        "document_type": "Unknown",
        "company_name": "<extracted company name>"
    }```"""
    
    # Fix: Convert dictionary objects to strings before joining
    candidate_labels_str = "\n".join([str(label) for label in candidate_labels])
    
    message = HumanMessage(
        content=[
            {"type": "text", "text": LABEL_PROMPT},
            {"type": "text", "text": candidate_labels_str},
        ]
    )
    
    chain = model | JsonOutputParser()
    
    return chain.invoke([message])

def generate_new_name(company_name: str, document_type: str):
    # Fix: Add input validation
    if not company_name or not document_type:
        raise ValueError("Company name and document type cannot be empty")
    
    # Clean company name - remove special characters and convert to snake case
    clean_company_name = re.sub(r'[^a-zA-Z0-9]+', '_', company_name).strip('_').lower()
    
    # Convert input to lowercase for case-insensitive matching
    doc_type_lower = document_type.lower()
    
    # Pattern matching dictionary with regex patterns
    pattern_matches = {
        r'.*bulletin.*': 'weekly_bulletin',
        r'.*regulatory.*report.*': 'monthly_regulatory_report',
        r'.*shareholder.*(?:circular|letter).*|.*(?:circular|letter).*shareholder.*': 'circular_letter_to_shareholders',
        r'.*prospectus.*': 'prospectus',
        r'.*(?:appointment|change|disposal|resignation|trading).*': 'notice_of_change',
        r'.*dividend.*(?:consideration|declaration).*': 'notice_of_dividend',
        r'.*(?:annual|quarterly).*(?:financial|statement).*': 'financial_statements',
        r'.*special.*circular.*': 'special_circular',
        r'.*merger.*': 'merger_notices',
        r'.*nav.*': 'nav_reports',
        r'.*annual.*meeting.*': 'annual_meeting_documents',
        r'.*ipo.*': 'ipo_prospectus',
        r'.*apo.*': 'apo_prospectus',
        r'.*rights.*issue.*': 'rights_issue',
        r'.*take.*over.*bid.*': 'take_over_bid',
        r'.*notice.*': 'notice',
    }
    
    # Find matching pattern
    new_type = None
    for pattern, value in pattern_matches.items():
        if re.match(pattern, doc_type_lower):
            new_type = value
            break
    
    # If no match found, create a fallback format
    if new_type is None:
        # Convert document type to snake case
        new_type = re.sub(r'[^a-z0-9]+', '_', doc_type_lower).strip('_')
    
    return f"{clean_company_name} - {new_type}.pdf"

if __name__ == "__main__":
    try:
        files = list_s3_files()
        results = []
        total_files = len(files)
        
        logger.info(f"Starting processing of {total_files} files")
        start_time = time.time()
        
        for index, file in enumerate(files, 1):
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            logger.info(f"Processing file {index}/{total_files} ({(index/total_files)*100:.1f}%) - Elapsed time: {elapsed_time:.1f}s")
            logger.info(f"Current file: {file}")
            
            try:
                # Add timeout to extract_pages
                start_process = time.time()
                img_binaries = extract_pages(file)
                if time.time() - start_process > 300:  # 5 minute timeout
                    logger.warning(f"Processing timeout for file {file}")
                    continue
                    
                candidate_labels = []
                
                for img in img_binaries:
                    label = get_candidate_labels(img)
                    candidate_labels.append(label)
                
                # if there is more than one candidate label, final label is the last one
                final_label = candidate_labels[-1]
                
                # final_label = label_document(candidate_labels)
                # logger.info(f"Final label before generating name: {final_label}")
                
                # # Rest of validation
                # if not isinstance(final_label, dict):
                #     logger.error(f"Unexpected final_label type: {type(final_label)}")
                #     continue
                    
                # if 'company_name' not in final_label or 'document_type' not in final_label:
                #     logger.error(f"Missing required fields in final_label: {final_label}")
                #     continue
                
                new_name = generate_new_name(
                    str(final_label.get('company_name', '')),
                    str(final_label.get('document_type', ''))
                )
                
                # Store the filename pair
                results.append({
                    'original_name': file,
                    'new_name': new_name
                })
                
                logger.info(f"Original file: {file}")
                logger.info(f"New name: {new_name}")
                
            except Exception as e:
                logger.error(f"Error processing file {file}: {str(e)}")
                continue
            
            # Add periodic status updates
            if index % 5 == 0:  # Log status every 5 files
                logger.info(f"Status update - Processed {index}/{total_files} files")
                logger.info(f"Last successful file: {file}")
        
        # Export results to CSV
        csv_path = 'filename_mapping.csv'
        try:
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = ['original_name', 'new_name']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(results)
                
            logger.info(f"Successfully exported filename mapping to {csv_path}")
        except Exception as e:
            logger.error(f"Error writing CSV file: {str(e)}")
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        # Save partial results to CSV
        if results:
            with open('partial_results.csv', 'w', newline='') as csvfile:
                fieldnames = ['original_name', 'new_name']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            logger.info("Partial results saved to partial_results.csv")
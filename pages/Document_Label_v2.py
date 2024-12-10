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
import asyncio
from asyncio import Queue, Semaphore
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, List, Callable, TypeVar, Any
from functools import partial
import aiohttp
import random
from tqdm.asyncio import tqdm
from tqdm import tqdm as tqdm_sync
import urllib3
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import CSVLoader
from langchain_google_vertexai import VertexAIEmbeddings
from botocore.config import Config

T = TypeVar('T')  # For generic return type

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

# Configure connection pooling
config = Config(
    max_pool_connections=50,  # Increase from default 10
    retries={'max_attempts': 3}
)

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("JSE_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("JSE_SECRET_ACCESS_KEY"),
    config=config
)

source_s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("JSE_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("JSE_SECRET_ACCESS_KEY"),
    config=config
)

target_s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION"),
    config=config
)

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

def generate_new_name(company_name: str, symbol: str, document_type: str):
    """
    Generate new name and partition path for the document
    Returns tuple of (partition_path, new_filename)
    """
    # Fix: Add input validation
    if not company_name or not symbol or not document_type:
        raise ValueError("Company name, symbol, and document type cannot be empty")
    
    # Clean company name - remove special characters and convert to snake case
    clean_company_name = re.sub(r'[^a-zA-Z0-9]+', '_', company_name).strip('_').lower()
    symbol = symbol.lower()
    document_type = document_type.lower()
    
    # Generate the partition path and filename
    partition_path = f"{clean_company_name}/{document_type}"
    new_filename = f"{clean_company_name}_{symbol}_{document_type}.pdf"
    
    return partition_path, new_filename

@dataclass
class WorkItem:
    file_path: str
    status: str = 'pending'
    result: Optional[dict] = None
    error: Optional[str] = None

class RateLimiter:
    def __init__(self, calls_per_second: float = 2.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = datetime.min
        self.semaphore = Semaphore(3)  # Max concurrent API calls
    
    async def acquire(self):
        await self.semaphore.acquire()
        now = datetime.now()
        
        # Calculate time since last call
        elapsed = (now - self.last_call).total_seconds()
        if elapsed < self.min_interval:
            # Wait if we're calling too frequently
            await asyncio.sleep(self.min_interval - elapsed)
        
        self.last_call = datetime.now()
    
    def release(self):
        self.semaphore.release()

class RetryWithExponentialBackoff:
    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        delay = self.initial_delay
        last_exception = None

        for retry in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {retry + 1} failed: {str(e)}")

                if retry == self.max_retries - 1:
                    logger.error(f"Max retries ({self.max_retries}) reached")
                    raise last_exception

                # Calculate delay with optional jitter
                if self.jitter:
                    delay *= (1 + random.random())
                
                # Apply backoff factor and cap at max_delay
                delay = min(delay * self.backoff_factor, self.max_delay)
                
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)

        raise last_exception

class DocumentProcessor:
    def __init__(
        self, 
        num_workers: int = 5, 
        batch_size: int = 10, 
        calls_per_second: float = 2.0,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
        max_retries: int = 3
    ):
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.work_queue = Queue()
        self.result_queue = Queue()
        self.workers: List[asyncio.Task] = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.results = []
        self.rate_limiter = RateLimiter(calls_per_second)
        self.retry_handler = RetryWithExponentialBackoff(
            initial_delay=initial_retry_delay,
            max_delay=max_retry_delay,
            max_retries=max_retries
        )
        self.total_files = 0
        self.progress_bar = None
        self.batch_progress = None
        self.company_db = None  # Will store the FAISS database
        self.doc_type_db = None  # Will store the FAISS database
        
    async def initialize_company_search(self):
        """Initialize the FAISS database for company search"""
        loader = CSVLoader(file_path="listed_companies - Sheet1.csv")
        docs = loader.load()
        embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004"
        )
        self.company_db = FAISS.from_documents(docs, embeddings)
    
    async def initialize_doc_type_search(self):
        """Initialize the FAISS database for document type search"""
        loader = CSVLoader(file_path="Naming_Convention_Documents - Copy of Copy of Tagged Documents.csv")
        docs = loader.load()
        embeddings = VertexAIEmbeddings(
            model_name="text-embedding-004"
        )
        self.doc_type_db = FAISS.from_documents(docs, embeddings)

    async def search_company(self, query_text: str):
        """Search for company name and symbol"""
        if self.company_db is None:
            await self.initialize_company_search()
            
        # Perform similarity search
        docs = await self.company_db.asimilarity_search(query_text, k=1)

        # Extract company and symbol from the result
        content = docs[0].page_content
        company = content.split('\n')[0].replace('Company: ', '').strip()
        symbol = content.split('\n')[1].replace('Symbol: ', '').strip()
        
        return company, symbol
    
    async def search_doc_type(self, query_text: str):
        """Search for document type"""
        if self.doc_type_db is None:
            await self.initialize_doc_type_search()
            
        # Perform similarity search
        docs = await self.doc_type_db.asimilarity_search(query_text, k=1)

        # Extract document type from the result
        content = docs[0].page_content
        doc_type = content.split('\n')[1].replace('Document Type: ', '').strip()
        
        return doc_type

    async def call_api_with_retry(self, img_binary: bytes):
        """Make API call with retry logic"""
        async def api_call():
            img_base64 = base64.b64encode(img_binary).decode('utf-8')
            
            model = ChatVertexAI(
                model="gemini-1.5-flash-001",
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            )

            data_url = f"data:image/png;base64,{img_base64}"
            message = HumanMessage(content=[
                {"type": "text", "text": LABEL_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ])
            
            chain = model | JsonOutputParser()
            initial_result = await chain.ainvoke([message])

            # Get the initial company name from the API response
            initial_company = initial_result.get('company_name', '')
            
            # Search for the correct company name
            try:
                company_name, symbol = await self.search_company(initial_company)
                doc_type = await self.search_doc_type(initial_company)
                # Update the result with the corrected company name
                initial_result['company_name'] = company_name
                initial_result['symbol'] = symbol
                initial_result['document_type'] = doc_type
            except Exception as e:
                logger.warning(f"Company name search failed: {str(e)}. Using original name.")
                initial_result['symbol'] = "unknown"
                initial_result['document_type'] = "unknown"

            return initial_result

        return await self.retry_handler.execute(api_call)

    async def get_candidate_labels_with_rate_limit(self, img_binary: bytes):
        """Rate-limited version of get_candidate_labels with retry logic"""
        try:
            await self.rate_limiter.acquire()
            return await self.call_api_with_retry(img_binary)
        finally:
            self.rate_limiter.release()

    async def upload_to_new_bucket(self, original_key: str, company_name: str, symbol: str, document_type: str) -> bool:
        """
        Upload renamed document to new bucket using different credentials with partitioning
        Args:
            original_key: Original S3 key
            company_name: Clean company name for partitioning
            symbol: Symbol for partitioning
            document_type: Document type for partitioning
        Returns:
            bool: True if successful, False otherwise
        """
        source_bucket = os.getenv("S3_BUCKET_NAME")
        target_bucket = os.getenv("S3_TARGET_BUCKET")  # This should be just the bucket name, not s3:// prefix
        
        try:
            # Generate partition path and filename
            partition_path, new_filename = generate_new_name(company_name, symbol, document_type)
            full_key = f"{partition_path}/{new_filename}"
            
            # Create temporary file path
            temp_path = f'/tmp/{new_filename}'
            
            # Download from source bucket
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: source_s3.download_file(
                    source_bucket,
                    original_key,
                    temp_path
                )
            )
            
            # Upload to target bucket with partition path
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: target_s3.upload_file(
                    temp_path,
                    target_bucket,
                    full_key
                )
            )
            
            logger.info(f"Successfully copied {original_key} to {target_bucket}/{full_key}")
            return True, full_key
            
        except Exception as e:
            logger.error(f"Failed to copy {original_key} to new bucket: {str(e)}")
            return False, None
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def worker(self, worker_id: int):
        """Worker process that handles file processing"""
        logger.info(f"Worker {worker_id} started")
        
        while True:
            try:
                work_item: WorkItem = await self.work_queue.get()
                
                try:
                    logger.info(f"Worker {worker_id} processing {work_item.file_path}")
                    
                    # Process PDF in thread pool with retry and progress
                    try:
                        img_binaries = await self.retry_handler.execute(
                            asyncio.get_event_loop().run_in_executor,
                            self.executor,
                            extract_pages,
                            work_item.file_path
                        )
                    except Exception as e:
                        logger.error(f"Failed to process PDF after retries: {str(e)}")
                        raise

                    # Process images with rate limiting and retry logic
                    tasks = []
                    for img in img_binaries:
                        task = self.get_candidate_labels_with_rate_limit(img)
                        tasks.append(task)
                    
                    try:
                        candidate_labels = await asyncio.gather(*tasks)
                    except Exception as e:
                        logger.error(f"Failed to process images after retries: {str(e)}")
                        raise

                    # Get final label
                    final_label = candidate_labels[-1]
                    company_name = str(final_label.get('company_name', ''))
                    symbol = str(final_label.get('symbol', ''))
                    document_type = str(final_label.get('document_type', ''))

                    # Upload to new bucket with partitioning
                    upload_success, full_key = await self.upload_to_new_bucket(
                        work_item.file_path,
                        company_name,
                        symbol,
                        document_type
                    )

                    # Store result with upload status and full path
                    work_item.status = 'completed' if upload_success else 'upload_failed'
                    work_item.result = {
                        'original_name': work_item.file_path,
                        'new_path': full_key,
                        'upload_status': 'success' if upload_success else 'failed'
                    }

                except Exception as e:
                    work_item.status = 'failed'
                    work_item.error = str(e)
                    logger.error(f"Worker {worker_id} error processing {work_item.file_path}: {e}")

                finally:
                    if self.batch_progress:
                        self.batch_progress.update(1)
                    await self.result_queue.put(work_item)
                    self.work_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} shutting down")
                break

    async def result_collector(self):
        """Collects and processes results from workers"""
        while True:
            try:
                result = await self.result_queue.get()
                if result.status == 'completed' and result.result:
                    self.results.append(result.result)
                    if self.progress_bar:
                        self.progress_bar.update(1)
                self.result_queue.task_done()
                
                # Periodically save results
                if len(self.results) % 10 == 0:
                    await self.save_partial_results()
                    
            except asyncio.CancelledError:
                break

    async def save_partial_results(self):
        """Save current results to CSV"""
        if not self.results:
            return
            
        try:
            with open('filename_mapping.csv', 'w', newline='') as csvfile:
                fieldnames = ['original_name', 'new_path', 'upload_status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    async def process_files(self, files: List[str]):
        """Main processing method"""
        self.total_files = len(files)
        
        try:
            # Initialize company search database
            await self.initialize_company_search()
            await self.initialize_doc_type_search()
            
            # Initialize progress bar for overall progress
            with tqdm_sync(
                total=self.total_files,
                desc="Overall Progress",
                unit="files",
                position=0,
                leave=True
            ) as self.progress_bar:
                
                # Start workers
                self.workers = [
                    asyncio.create_task(self.worker(i))
                    for i in range(self.num_workers)
                ]
                
                # Start result collector
                collector = asyncio.create_task(self.result_collector())

                # Process files in batches with progress bar
                for i in range(0, len(files), self.batch_size):
                    batch = files[i:i + self.batch_size]
                    batch_desc = f"Batch {i//self.batch_size + 1}/{(len(files) + self.batch_size - 1)//self.batch_size}"
                    
                    # Initialize progress bar for current batch
                    with tqdm_sync(
                        total=len(batch),
                        desc=batch_desc,
                        unit="files",
                        position=1,
                        leave=False
                    ) as self.batch_progress:
                        # Add files to work queue
                        for file in batch:
                            await self.work_queue.put(WorkItem(file_path=file))
                            
                        # Wait for batch to complete
                        await self.work_queue.join()
                        self.batch_progress.update(len(batch))

                # Wait for all results to be processed
                await self.result_queue.join()

                # Cancel workers and collector
                for worker in self.workers:
                    worker.cancel()
                collector.cancel()

                # Wait for workers to shut down
                await asyncio.gather(*self.workers, collector, return_exceptions=True)

                # Save final results
                await self.save_partial_results()
            
        finally:
            self.executor.shutdown()

async def process_single_file(file: str, executor: ThreadPoolExecutor):
    """
    Process a single file asynchronously
    """
    try:
        # Run CPU-intensive PDF operations in thread pool
        img_binaries = await asyncio.get_event_loop().run_in_executor(
            executor, 
            extract_pages, 
            file
        )
        
        # Process images concurrently
        tasks = [
            get_candidate_labels_async(img)
            for img in img_binaries
        ]
        candidate_labels = await asyncio.gather(*tasks)
        
        # Get final label and generate new name
        final_label = candidate_labels[-1]
        new_name = generate_new_name(
            str(final_label.get('company_name', '')),
            str(final_label.get('document_type', ''))
        )
        
        return {
            'original_name': file,
            'new_name': new_name
        }
    except Exception as e:
        logger.error(f"Error processing file {file}: {str(e)}")
        return None

async def get_candidate_labels_async(img_binary: bytes):
    """
    Async version of get_candidate_labels
    """
    img_base64 = base64.b64encode(img_binary).decode('utf-8')
    
    model = ChatVertexAI(
        model="gemini-1.5-flash-001",
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    data_url = f"data:image/png;base64,{img_base64}"
    
    message = HumanMessage(content=[
        {"type": "text", "text": LABEL_PROMPT},
        {"type": "image_url", "image_url": {"url": data_url}},
    ])
    
    chain = model | JsonOutputParser()
    response = await chain.ainvoke([message])
    return response

async def main():
    try:
        # Get list of files
        print("Fetching files from S3...")
        files = list_s3_files()
        # total_files = len(files)
        # Select first 100 files
        files = files[:100]
        total_files = len(files)
        
        print(f"\nStarting processing of {total_files} files")
        print("Progress bars will show overall progress and current batch progress\n")

        # Create processor with desired settings
        processor = DocumentProcessor(
            num_workers=10,
            batch_size=10,
            calls_per_second=2.0,
            initial_retry_delay=1.0,
            max_retry_delay=60.0,
            max_retries=3
        )
        
        # Process files with progress tracking
        start_time = time.time()
        await processor.process_files(files)
        
        elapsed_time = time.time() - start_time
        print(f"\nProcessing completed in {elapsed_time:.2f} seconds")
        print(f"Successfully processed {len(processor.results)} files")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        # Results will be saved by the processor

if __name__ == "__main__":
    asyncio.run(main())
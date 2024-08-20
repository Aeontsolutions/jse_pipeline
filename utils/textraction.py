from os import environ
import re
from pdf2image import convert_from_path
from textractor import Textractor
from textractor.data.constants import TextractFeatures
from textractor.utils.s3_utils import upload_to_s3


def find_matching_tables(document, desired_patterns):
    matching_tables = []

    for table in document.tables:
        if table.title and any(re.search(pattern, table.title.text, re.IGNORECASE) for pattern in desired_patterns):
            matching_tables.append(table)

    return matching_tables

def get_table_by_page(matching_tables, page_num):
    for table in matching_tables:
        if table.page == page_num:
            return table.to_pandas(use_columns=True)

    # return None

def extract_tables_from_document(selected_file_path):
    extractor = Textractor(region_name=environ.get('AWS_DEFAULT_REGION'))
    s3_output_bucket = environ.get('S3_BUCKET_NAME')

    document = extractor.start_document_analysis(
      file_source=selected_file_path,
      features=[TextractFeatures.TABLES],
      s3_output_path=s3_output_bucket,
      save_image=True
    )

    desired_patterns = (r'comprehensive income', r'financial position', r'cash flow')
    tables_found = find_matching_tables(document, desired_patterns)
    
    return tables_found

if __name__ == "__main__":
    pass
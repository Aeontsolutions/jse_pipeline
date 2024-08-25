from os import environ
import re
from textractor import Textractor
from textractor.data.constants import TextractFeatures


def find_matching_tables(document, desired_patterns):
    matching_tables = []

    for table in document.tables:
        if table.title and any(re.search(pattern, table.title.text, re.IGNORECASE) for pattern in desired_patterns):
            matching_tables.append(table)

    return matching_tables

def get_table_by_page(matching_tables, page_num):
    for table in matching_tables:
        if table.page == page_num:
            return (table.title.text,
                    table.to_pandas(use_columns=True))

    # return None

def extract_tables_from_document(selected_file_path, desired_patterns):
    extractor = Textractor(region_name=environ.get('AWS_DEFAULT_REGION'))
    s3_output_bucket = environ.get('S3_BUCKET_NAME')

    document = extractor.start_document_analysis(
      file_source=f"s3://jse-bi-bucket/{selected_file_path}",
      features=[TextractFeatures.TABLES],
      s3_output_path=s3_output_bucket,
      save_image=True
    )
    tables_found = find_matching_tables(document, desired_patterns)
    
    return tables_found

if __name__ == "__main__":
    pass
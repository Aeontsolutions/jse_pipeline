import pandas as pd
import numpy as np
import re

def rename_columns_from_row(dataframe):
    row_index = input("Enter the row index to use for renaming columns (or 'none'): ")

    if row_index.lower() == "none":
        return dataframe

    try:
        row_index = int(row_index)
    except ValueError:
        print("Invalid input. Please enter a valid row index.")
        return dataframe

    if 0 <= row_index < len(dataframe):
        new_columns = dataframe.iloc[row_index].tolist()
        new_dataframe = dataframe.copy()
        new_dataframe.columns = new_columns
        new_dataframe = new_dataframe.drop(new_dataframe.index[row_index])
        return new_dataframe
    else:
        print("Invalid row index.")
        return dataframe

def flatten_columns(df):
    # Create a copy of the DataFrame to avoid modifying the original
    df_copy = df.copy()

    # Forward fill the NaN or empty cells in the first row with the previous non-empty cell value
    df_copy.iloc[0] = df_copy.iloc[0].replace('', np.nan).fillna(method='ffill')

    # Set the column names
    df_copy.columns = pd.MultiIndex.from_arrays([
        df_copy.iloc[0].fillna(''),
        df_copy.iloc[1].fillna('')
    ])

    # Drop the rows that were used for column names
    df_copy = df_copy.drop([0, 1]).reset_index(drop=True)

    # Flatten the multi-level columns
    df_copy.columns = [' '.join([str(a) for a in col]).strip() for col in df_copy.columns.values]

    return df_copy

def set_column_names(df):
    nested = input("Are the column headers nested? (y/n): ")

    if nested.lower() == 'y':
        return flatten_columns(df)
    elif nested.lower() == 'n':
        return rename_columns_from_row(df)
    else:
        print("Invalid input. Please enter 'y' or 'n'.")
        return df

def rename_column(dataframe):
    column_index = input("Enter the index of the column to rename as: ")
    new_column_name = input("Enter the new column name: ")  # Fixed the quotation marks here
    try:
        column_index = int(column_index.strip())  # Convert to integer
    except ValueError:
        print("Invalid input. Please enter a valid integer.")
        return dataframe

    if 0 <= column_index < len(dataframe.columns):
        new_columns = dataframe.columns.tolist()  # Convert the column index to a list
        new_columns[column_index] = new_column_name  # Rename only the column at the specified index
        dataframe.columns = new_columns  # Assign the new column names back to the DataFrame
        return dataframe
    else:
        print("Invalid column index.")
        return dataframe
    
def drop_columns(df):
    column_pos = input("Enter the column index you want to drop (comma-separated) or 'none': ")
    if column_pos.strip().lower() == "none":
        return df
    else:
        return df.drop(columns=df.columns[int(column_pos.strip())])
    
def melt_dataframe(df):
    # Use 'account_item' as the ID column
    id_columns = ['account_item']

    # Use all other columns as Value columns
    value_columns = [col for col in df.columns if col != 'account_item']

    # Melt the dataframe
    melted_df = pd.melt(df, id_vars=id_columns, value_vars=value_columns,
                        var_name='report', value_name='value')

    # Replace empty strings with "0" as a string
    melted_df['value'] = melted_df['value'].apply(lambda x: "0" if pd.isna(x) or x == '' else str(x))

    return melted_df

def clean_currency_column(df, column_name="value"):

  # replace '$' with ''
  df['value'] = df['value'].str.replace('[$ a-zA-Z*]', '', regex=True)
  # Remove duplicate symbols
  df['value'] = df['value'].apply(remove_duplicate_symbols)

  # Then use janitor to clean the currency column
  try:
    df = df.currency_column_to_numeric(
        column_name,
        cleaning_style="accounting",
        remove_non_numeric=True)
  except Exception as e:
        print(f"An error occurred: {e}")

  return df

def remove_duplicate_symbols(s):
    return re.sub(r'([()$ a-zA-Z])\1+', r'\1', s)

# defing a function that asks the user if the values should be multiplied by 1000 and then performs the multiplication if the user says yes
def multiply_by_1000(dataframe, value_column):
  should_multiply = input("Do you want to multiply by 1000? (y/n)")
  if should_multiply == "y":
    dataframe[value_column] = dataframe[value_column] * 1000
    dataframe['report'] = dataframe['report'].str.replace("'000", '', regex=True)
  return dataframe

# define a function that indicates the currency of the statement
def add_currency_column(dataframe):
  currency = input("What is the currency of the statement?")
  dataframe['Currency'] = currency.strip().upper()
  return dataframe

# define a function that adds a column that indicates if the statement was audited or not
def add_audit_column(dataframe):
  was_audit = input("Was the statement audited? (y/n)")
  if was_audit == "y":
    dataframe['audit'] = True
  return dataframe

# define a function that adds a column that indicates the company
def add_company_ticker_column(dataframe):
  ticker = input("What is the company ticker?")
  dataframe['ticker'] = ticker.strip().upper()
  return dataframe

# define a function that adds a column that indicates the statement
def add_statement_column(dataframe):
  statement = input("What is the statement?")
  dataframe['Statement'] = statement
  return dataframe

def update_dataframe_value(df):
    while True:
        # Check if the user wants to update the value
        update_value = input("Do you want to update a value? (y/n) ")
        if update_value == "n":
            break

        # Step 1: Provide a numbered list of unique values in the 'account_item' column
        unique_account_items = df['account_item'].unique()
        for i, item in enumerate(unique_account_items):
            print(f"{i+1}. {item}")

        # Step 2: Allow the user to enter the number of an account item
        selected_number = int(input("Enter the number corresponding to the account item you want to update: "))
        if selected_number < 1 or selected_number > len(unique_account_items):
            print("Invalid number. Exiting.")
            continue

        selected_account_item = unique_account_items[selected_number - 1]

        # New Step 1: Display a numbered list of unique items in the 'report' column
        unique_reports = df[df['account_item'] == selected_account_item]['report'].unique()
        for i, report in enumerate(unique_reports):
            print(f"{i+1}. {report}")

        # New Step 2: Allow the user to enter the number of the report item
        selected_report_number = int(input("Enter the number corresponding to the report you want to update: "))
        if selected_report_number < 1 or selected_report_number > len(unique_reports):
            print("Invalid number. Exiting.")
            continue

        selected_report = unique_reports[selected_report_number - 1]

        # Step 3: Enter the correct value that should be in the DataFrame
        new_value = float(input(f"Enter the new value for '{selected_account_item}' in report '{selected_report}': "))

        # Step 4: Update the value of that account item and report
        df.loc[(df['account_item'] == selected_account_item) & (df['report'] == selected_report), 'value'] = new_value

    # Step 5: Return the updated DataFrame
    return df

if __name__ == "__main__":
    # This block is for testing the functions individually if needed
    pass

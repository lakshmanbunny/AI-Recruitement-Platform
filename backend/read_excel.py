import pandas as pd
import sys

file_path = r"c:\Users\lakshman.yvs\Desktop\exp\ParadigmIT.xlsx"

try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    print("\nFirst 2 rows:")
    print(df.head(2).to_dict('records'))
except Exception as e:
    print(f"Error reading excel: {e}")

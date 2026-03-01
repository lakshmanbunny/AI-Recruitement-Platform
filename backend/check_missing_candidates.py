import os
import sys
import pandas as pd

# Setup paths so we can import backend models
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, "../"))
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from app.db.database import SessionLocal
from app.db import models

def tally_candidates():
    excel_file = os.path.join(project_root, "ParadigmIT.xlsx")
    
    # 1. Get Roll Numbers from Excel
    print(f"Reading {excel_file}...")
    df = pd.read_excel(excel_file)
    
    # Clean and extract all non-empty roll numbers
    df_clean = df.dropna(subset=['Roll Number']).copy()
    excel_rolls = df_clean['Roll Number'].astype(str).str.strip().str.upper().tolist()
    
    # Detailed counts
    total_rows = len(df)
    empty_roll_rows = df['Roll Number'].isna().sum()
    unique_excel_rolls = set(excel_rolls)
    
    print("\n--- EXCEL STATS ---")
    print(f"Total rows in Excel: {total_rows}")
    print(f"Rows with empty/missing Roll Number: {empty_roll_rows}")
    print(f"Total valid roll numbers found: {len(excel_rolls)}")
    print(f"Unique roll numbers found: {len(unique_excel_rolls)}")
    
    if len(excel_rolls) > len(unique_excel_rolls):
        print(f"Number of duplicate entries in Excel: {len(excel_rolls) - len(unique_excel_rolls)}")
        
        # Identify the duplicates
        dupes = df_clean[df_clean.duplicated(subset=['Roll Number'], keep=False)]
        print("\nDuplicates found in Excel:")
        for _, row in dupes.iterrows():
            print(f"  - {row['Roll Number']}: {row['Full Name']} ({row['Email ID (Personal)']})")

    # 2. Get Roll Numbers from DB
    db = SessionLocal()
    try:
        db_candidates = db.query(models.WoxsenCandidate.roll_number).all()
        db_rolls = {str(c[0]).strip().upper() for c in db_candidates}
        
        print("\n--- DATABASE STATS ---")
        print(f"Total candidates in Database: {len(db_rolls)}")
        
        # 3. Tally missing
        missing_from_db = unique_excel_rolls - db_rolls
        missing_from_excel = db_rolls - unique_excel_rolls
        
        print("\n--- RECONCILIATION ---")
        if not missing_from_db and not missing_from_excel:
            print("✅ PERFECT MATCH! All unique candidates from the Excel sheet are in the Database.")
        else:
            if missing_from_db:
                print(f"❌ Found {len(missing_from_db)} candidates IN EXCEL but MISSING FROM DB:")
                for r in missing_from_db:
                    print(f"  - {r}")
                    
            if missing_from_excel:
                print(f"⚠️ Found {len(missing_from_excel)} candidates IN DB but MISSING FROM EXCEL (Likely manual additions):")
                for r in missing_from_excel:
                    print(f"  - {r}")
                
    finally:
        db.close()

if __name__ == "__main__":
    tally_candidates()

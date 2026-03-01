import os
import shutil
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Note: We are running this from backend/
DATABASE_URL = "sqlite:///paradigm_ai.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def clear_dummy_data():
    session = SessionLocal()
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    
    # We carefully DO NOT include 'woxsen_candidates' or 'users' or 'job_descriptions'
    tables_to_keep = ["woxsen_candidates", "users", "job_descriptions", "alembic_version"]
    tables_to_clear = [t for t in all_tables if t not in tables_to_keep]
    
    try:
        # Delete from tables, ignoring errors if foreign keys block (SQLite default is off but just in case)
        # We process them backward to generally hit child tables first
        for table_name in reversed(tables_to_clear):
            print(f"Clearing table: {table_name}")
            try:
                session.execute(text(f"DELETE FROM {table_name}"))
            except Exception as e:
                print(f"  Skipping {table_name}: {e}")
                session.rollback()
            
        session.commit()
        print("✅ Database dummy tables cleared successfully.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error clearing database: {e}")
    finally:
        session.close()

def clear_storage_directories():
    base_dir = os.path.dirname(__file__)
    storage_dir = os.path.join(base_dir, "storage")
    
    if os.path.exists(storage_dir):
        print(f"Clearing storage directory: {storage_dir}")
        for item in os.listdir(storage_dir):
            if item == "embedding_cache.json":
                print(f"  Keeping cache: {item}")
                continue
            item_path = os.path.join(storage_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"  Deleted dir: {item}")
                else:
                    os.remove(item_path)
                    print(f"  Deleted file: {item}")
            except Exception as e:
                print(f"  ❌ Error deleting {item}: {e}")
        print("✅ Storage directory wiped successfully.")
    else:
        print("Storage directory does not exist.")

if __name__ == "__main__":
    print("--- 🧹 Starting Cleanup ---\n")
    clear_dummy_data()
    print("\n")
    clear_storage_directories()
    print("\n--- ✨ Cleanup Complete ---")

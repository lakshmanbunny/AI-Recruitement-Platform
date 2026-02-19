from .database import engine, Base
from . import models

def init_db():
    print("--- [DB] Initializing Database Schema... ---")
    Base.metadata.create_all(bind=engine)
    print("--- [DB] Database Schema Synchronized. ---")

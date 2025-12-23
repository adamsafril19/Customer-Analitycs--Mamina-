"""
Script untuk verifikasi tabel yang sudah dibuat di database
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("=" * 50)
print("📋 DAFTAR TABEL DI DATABASE")
print("=" * 50)

inspector = inspect(engine)
tables = inspector.get_table_names()

for i, table in enumerate(tables, 1):
    print(f"\n{i}. 📁 {table}")
    
    # Get columns
    columns = inspector.get_columns(table)
    for col in columns:
        nullable = "NULL" if col['nullable'] else "NOT NULL"
        print(f"   - {col['name']}: {col['type']} ({nullable})")

print("\n" + "=" * 50)
print(f"✅ Total: {len(tables)} tabel berhasil dibuat!")
print("=" * 50)

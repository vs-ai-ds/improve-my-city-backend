# File: test_con.py
# Project: improve-my-city-backend
# Auto-added for reference

from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

load_dotenv(override=True)

url = os.getenv("DATABASE_URL")
print("DATABASE_URL =", url)  # sanity check - should show your Supabase URL

engine = create_engine(url, pool_pre_ping=True)

with engine.connect() as conn:
    print("select 1 ->", conn.scalar(text("select 1")))
    print("server version ->", conn.scalar(text("select version()")))
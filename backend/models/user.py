"""
models/user.py

Pydantic models for user identity and usage tracking.

Models:
  - User: authenticated user with id and email from Supabase JWT
  - UsageRecord: tracks analysis count per user per month (maps to user_usage table)
"""

from pydantic import BaseModel
from datetime import datetime

class User(BaseModel):
    id: str
    email: str

class UsageRecord(BaseModel):
    user_id: str
    analysis_count: int
    month: str          # "YYYY-MM"
    updated_at: datetime

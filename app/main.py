"""
Entrypoint module for uvicorn.

Run as:

    uvicorn app.main:app --reload
"""

from app.api import app  # FastAPI app

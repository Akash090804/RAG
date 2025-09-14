# File: app/main.py

import asyncio
import sys
from fastapi import FastAPI
from app.routers import api
# This is the patch for the Playwright asyncio error on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



app = FastAPI(
    title="Web Content Processing API",
    description="A generalized API to extract information from URLs and solve specific web challenges.",
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
)

app.include_router(api.router, prefix="/api")

@app.get("/", tags=["Root"])
def read_root():
    """
    A simple root endpoint to confirm that the API is running.
    """
    return {"status": "ok", "message": "Welcome to the API! Visit /docs for documentation."}
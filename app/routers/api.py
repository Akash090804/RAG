# File: app/routers/api.py

from fastapi import APIRouter, HTTPException, Body
from app.models.schemas import URLQuery, AnswersResponse
from app.services.scraper import process_url_query

# Create a new router object
router = APIRouter()

@router.post("/process", response_model=AnswersResponse, tags=["Processing"])
def process_url_endpoint(query: URLQuery = Body(...)):
    """
    A general-purpose endpoint to process a URL.

    - It accepts a URL and a list of questions.
    - It dispatches the request to the appropriate backend service.
    - It returns a list of answers corresponding to the questions.
    """
    if not query.url or not query.questions:
        raise HTTPException(
            status_code=400, 
            detail="Both 'url' and 'questions' fields are required."
        )

    try:
        # Delegate the core logic to the service layer
        answers = process_url_query(query)
        return AnswersResponse(answers=answers)
    except Exception as e:
        # A general catch-all for any unexpected errors during processing
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected internal error occurred: {str(e)}"
        )
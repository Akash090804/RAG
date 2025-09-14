# File: app/routers/api.py

from fastapi import APIRouter, HTTPException, Body, UploadFile, File, Form, Depends
from app.models.schemas import URLQuery, AnswersResponse, FileQuery
from typing import List
import os
from app.services.enhanced_rag import EnhancedRAG
from dotenv import load_dotenv

load_dotenv()

# Initialize RAG system
rag_system = EnhancedRAG(api_key=os.getenv("GEMINI_API_KEY"))


# Create a new router object
router = APIRouter()

@router.post("/upload", response_model=AnswersResponse, tags=["Processing"])
async def upload_file_endpoint(
    file: UploadFile = File(...),
    questions: List[str] = Form(...)
):
    """
    Upload and process a file (PDF, DOCX, PPT, etc.) with questions.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Check file size (limit to 100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes
    
    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 100MB")
        
        # Get file extension
        file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        supported_formats = {'pdf', 'docx', 'doc', 'pptx', 'ppt', 'txt', 'csv'}
        
        if file_ext not in supported_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported formats: {', '.join(supported_formats)}"
            )
        
        # Process file
        success = rag_system.process_file(content, file.filename, file_ext)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to process file")
        
        # Get answers for all questions
        answers = []
        for question in questions:
            result = rag_system.answer_question(question)
            answers.append(result['answer'])
        
        return AnswersResponse(answers=answers)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.post("/process", response_model=AnswersResponse, tags=["Processing"])
async def process_url_endpoint(query: URLQuery = Body(...)):
    """
    Process a URL and answer questions about its content.
    """
    try:
        # Fetch and process the URL content
        import requests
        response = requests.get(query.url)
        content = response.content
        
        # Process the webpage
        success = rag_system.process_file(
            content,
            query.url,
            'html'
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to process URL")
        
        # Get answers for all questions
        answers = []
        for question in query.questions:
            result = rag_system.answer_question(question)
            answers.append(result['answer'])
        
        return AnswersResponse(answers=answers)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")

# File: app/services/scraper.py

import logging
from app.models.schemas import URLQuery
from app.services.extractor import solve_hidden_code_challenge
from app.services.rag import answer_generic_question

logger = logging.getLogger(__name__)

def process_url_query(query: URLQuery) -> list[str]:
    """
    Processes a URL query by acting as a router, dispatching tasks
    to either a specialized extractor or a general QA service based on the question.
    """
    answers = []
    
    # Pre-solve for specific, non-textual data if it's the HackRx URL
    is_hackrx_url = "register.hackrx.in/showdown/startChallenge" in query.url
    if is_hackrx_url:
        specialized_data = solve_hidden_code_challenge(query.url)
    else:
        specialized_data = {}

    # Iterate through each question and decide which tool to use
    for question in query.questions:
        question_lower = question.lower()
        
        # --- Router Logic ---
        
        # Rule 1: If the question asks for a known, specific piece of hidden data, use the specialist.
        if is_hackrx_url and "challenge id" in question_lower:
            logger.info(f"Routing '{question}' to: Specialist Extractor (Challenge ID)")
            answers.append(specialized_data.get("challenge_id", "Not Found"))
            
        elif is_hackrx_url and "completion code" in question_lower:
            logger.info(f"Routing '{question}' to: Specialist Extractor (Completion Code)")
            answers.append(specialized_data.get("completion_code", "Not Found"))
            
        # Rule 2: For all other questions, use the general-purpose RAG service.
        else:
            logger.info(f"Routing '{question}' to: General RAG Service")
            # This handles the "What is the challenge name?" question, as that
            # answer is visible in the page text.
            generic_answer = answer_generic_question(query.url, question)
            answers.append(generic_answer)
            
    logger.info(f"Query processed. Final answers: {answers}")
    return answers
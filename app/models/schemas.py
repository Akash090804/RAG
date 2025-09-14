# File: app/schemas.py

from pydantic import BaseModel, Field
from typing import List, Any

class BaseQuery(BaseModel):
    """
    A generic base model for queries that can be extended.
    This promotes reusability.
    """
    pass

class URLQuery(BaseQuery):
    """
    Defines the structure for a query involving a URL and a set of questions.
    This is a common pattern for web scraping and information retrieval tasks.
    """
    url: str = Field(
        ..., 
        description="The URL of the target resource to be processed.",
        example="https://example.com/some-document.pdf"
    )
    questions: List[str] = Field(
        ..., 
        description="A list of questions to be answered based on the content of the URL.",
        example=["What is the main topic of this document?", "Who is the author?"]
    )

class BaseResponse(BaseModel):
    """
    A generic base model for API responses.
    """
    pass

class AnswersResponse(BaseResponse):
    """
    Defines the structure for a response that contains a list of answers.
    """
    answers: List[Any] = Field(
        ...,
        description="A list of answers corresponding to the list of questions in the query.",
        example=["The main topic is web scraping.", "The author is Jane Doe."]
    )
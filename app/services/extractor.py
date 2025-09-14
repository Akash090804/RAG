import requests
from bs4 import BeautifulSoup, Comment
import PyPDF2
from pptx import Presentation
import pandas as pd
from docx import Document
from io import BytesIO
from typing import Dict
import logging
from urllib.parse import urlparse
import pytesseract
from pdf2image import convert_from_bytes
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_content(url: str, headers: Dict[str, str] = None) -> bytes:
    """
    Fetch raw content from a URL using the requests library.
    """
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)
    try:
        logger.info(f"Fetching content with requests: {url}")
        response = requests.get(url, headers=default_headers, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        logger.error(f"Requests failed to fetch URL {url}: {e}")
        raise ValueError(f"Failed to fetch URL with requests: {e}")

def extract_text_from_content(content: bytes, url: str) -> str:
    """
    Extracts text from raw byte content based on the file type inferred from the URL.
    """
    parsed_url = urlparse(url)
    file_extension = parsed_url.path.split('.')[-1].lower() if '.' in parsed_url.path else ''
    logger.info(f"Extracting text for file type: {file_extension or 'html'}")
    try:
        if file_extension == 'pdf':
            try:
                # First try normal PDF text extraction
                with BytesIO(content) as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    total_pages = len(reader.pages)
                    logger.info(f"Processing PDF with {total_pages} pages")
                    
                    # Try normal text extraction first
                    for i, page in enumerate(reader.pages):
                        page_text = page.extract_text() or ''
                        if page_text.strip():
                            text += f"\n=== Page {i+1} ===\n{page_text}\n"
                    
                    # If no text was extracted, assume it's a scanned PDF and use OCR
                    if not text.strip():
                        logger.info("No text found with normal extraction, switching to OCR")
                        text = ""
                        
                        # Create a temporary directory for image processing
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # Convert PDF to images
                            logger.info("Converting PDF pages to images")
                            images = convert_from_bytes(
                                content,
                                output_folder=temp_dir,
                                fmt='png',
                                dpi=300  # Higher DPI for better quality
                            )
                            
                            # Process each page with OCR
                            for i, image in enumerate(images):
                                logger.info(f"Processing page {i+1} with OCR")
                                # Use OCR to extract text
                                page_text = pytesseract.image_to_string(
                                    image,
                                    lang='eng',
                                    config='--psm 1 --oem 3'  # Automatic page segmentation with LSTM OCR
                                )
                                
                                if page_text.strip():
                                    # Clean up OCR output
                                    page_text = ' '.join(page_text.split())  # Fix spacing
                                    page_text = page_text.replace('|', 'I')  # Common OCR fixes
                                    page_text = page_text.replace('{}', '')
                                    page_text = page_text.replace('  ', ' ')
                                    
                                    text += f"\n=== Page {i+1} ===\n{page_text}\n"
                                    logger.info(f"Successfully extracted text from page {i+1} using OCR")
                                else:
                                    logger.warning(f"No text found on page {i+1} after OCR")
                    
                    if not text.strip():
                        raise ValueError("No text could be extracted from the PDF using either method")
                    
                    # Post-process the entire text
                    text = text.replace('\n\n\n', '\n\n')  # Remove excessive newlines
                    text = text.replace('===', '\n===')  # Better page separation
                    
                    logger.info(f"Successfully extracted {len(text)} characters from PDF")
                    # Log a sample of the text for debugging
                    text_sample = text[:500] + "..." if len(text) > 500 else text
                    logger.info(f"Sample of extracted text: {text_sample}")
                    
                    return text
                    
            except Exception as e:
                logger.error(f"Error processing PDF: {str(e)}")
                raise ValueError(f"PDF processing failed: {str(e)}")
        elif file_extension in ['ppt', 'pptx']:
            with BytesIO(content) as f:
                prs = Presentation(f)
                return '\n'.join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, 'text'))
        elif file_extension in ['xls', 'xlsx']:
            with BytesIO(content) as f:
                df = pd.read_excel(f, engine='openpyxl')
                return df.to_string(index=False)
        elif file_extension == 'docx':
            with BytesIO(content) as f:
                doc = Document(f)
                return '\n'.join(para.text for para in doc.paragraphs)
        elif file_extension in ['txt', 'csv', 'json']:
            return content.decode('utf-8', errors='ignore')
        else:
            soup = BeautifulSoup(content, 'lxml')
            text = soup.get_text(separator='\n', strip=True)
            hidden_texts = [el.get_text(separator='\n', strip=True) for el in soup.find_all(style=lambda v: v and 'display:none' in v)]
            comments = [str(comment).strip() for comment in soup.find_all(string=lambda text: isinstance(text, Comment))]
            full_text = '\n'.join([text] + hidden_texts + comments)
            logger.info(f"Extracted HTML text length: {len(full_text)} chars")
            return full_text
    except Exception as e:
        logger.error(f"Failed to extract text from content for {url}: {e}")
        raise ValueError(f"Text extraction failed: {e}")
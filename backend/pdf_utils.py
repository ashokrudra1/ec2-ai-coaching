# backend/pdf_utils.py
import io
import logging
import re
from typing import Optional
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
    """
    Extracts plain text from raw PDF bytes.
    
    Args:
        pdf_bytes: Raw PDF file content
        max_pages: Maximum number of pages to extract (None = all pages)
    
    Returns:
        Extracted and cleaned text suitable for LLM processing
    """
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        # Limit pages if specified
        pages_to_read = reader.pages if not max_pages else reader.pages[:max_pages]
        
        text = ""
        for page_num, page in enumerate(pages_to_read):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {page_num + 1} ---\n{page_text}"
        
        cleaned_text = clean_extracted_text(text.strip())
        return cleaned_text
        
    except Exception as e:
        logger.exception(f"❌ Error extracting text from PDF bytes: {e}")
        return ""


def clean_extracted_text(text: str) -> str:
    """
    Cleans extracted PDF text for LLM processing.
    
    Performs:
    - Remove excessive whitespace and newlines
    - Normalize line breaks
    - Remove control characters
    - Collapse multiple spaces
    
    Args:
        text: Raw extracted text
    
    Returns:
        Cleaned text ready for LLM
    """
    if not text:
        return ""
    
    try:
        # Remove control characters except newline and tab
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize line breaks (multiple newlines -> single newline)
        text = re.sub(r'\n\n+', '\n', text)
        
        # Collapse multiple spaces but preserve paragraphs
        text = re.sub(r' +', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        logger.debug(f"Text cleaned: {len(text)} characters")
        return text
        
    except Exception as e:
        logger.error(f"Text cleaning failed: {e}")
        return text


def validate_pdf_bytes(pdf_bytes: bytes) -> tuple[bool, str]:
    """
    Validate that bytes represent a valid PDF file.
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    if not pdf_bytes:
        return False, "Empty PDF content"
    
    # Check PDF magic number (first 4 bytes should be "%PDF")
    if not pdf_bytes.startswith(b'%PDF'):
        return False, "Invalid PDF header"
    
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        if len(reader.pages) == 0:
            return False, "PDF has no pages"
        
        return True, ""
        
    except Exception as e:
        return False, f"Invalid PDF: {str(e)}"


def extract_medical_keywords(text: str) -> list[str]:
    """
    Extract potential medical/health keywords from text.
    Useful for categorizing uploaded documents.
    
    Args:
        text: Document text
    
    Returns:
        List of detected keywords
    """
    medical_keywords = [
        "doctor", "patient", "diagnosis", "symptom", "treatment",
        "medication", "prescription", "blood pressure", "heart rate",
        "cholesterol", "glucose", "diabetes", "asthma", "allergy",
        "infection", "injury", "surgery", "therapy", "test",
        "examination", "report", "lab", "x-ray", "ultrasound",
        "ecg", "ekg", "mri", "ct scan", "blood work"
    ]
    
    text_lower = text.lower()
    found_keywords = []
    
    for keyword in medical_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword)
    
    return list(set(found_keywords))  # Remove duplicates

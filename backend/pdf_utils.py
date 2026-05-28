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
        # Normalize CRLF/CR to LF first.
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Treat tabs as structural separators for extracted PDF fragments.
        text = text.replace("\t", "\n")

        # Remove control characters except newline.
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

        # Trim spaces around each line, then drop empty lines.
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]

        # Collapse extra intra-line whitespace.
        lines = [re.sub(r"\s{2,}", " ", line) for line in lines]

        cleaned = "\n".join(lines).strip()
        logger.debug("Text cleaned: %s characters", len(cleaned))
        return cleaned

    except (TypeError, ValueError) as e:
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
    keyword_patterns: dict[str, str] = {
        "doctor": r"\bdoctor(s)?\b",
        "patient": r"\bpatient(s)?\b",
        "diagnosis": r"\bdiagnos(is|es|ed|ing)\b",
        "symptom": r"\bsymptom(s)?\b",
        "treatment": r"\btreatment(s)?\b",
        "medication": r"\bmedication(s)?\b",
        "prescription": r"\bprescription(s)?\b",
        "blood pressure": r"\bblood pressure\b",
        "heart rate": r"\bheart rate\b",
        "cholesterol": r"\bcholesterol\b",
        "glucose": r"\bglucose\b",
        "diabetes": r"\bdiabetes\b",
        "asthma": r"\basthma\b",
        "allergy": r"\ballerg(y|ies)\b",
        "infection": r"\binfection(s)?\b",
        "injury": r"\binjur(y|ies)\b",
        "surgery": r"\bsurger(y|ies)\b",
        "therapy": r"\btherap(y|ies)\b",
        "test": r"\btest(s)?\b",
        "examination": r"\bexamination(s)?\b",
        "report": r"\breport(s)?\b",
        "lab": r"\blab(s)?\b",
        "x-ray": r"\bx[\s-]?ray(s)?\b",
        "ultrasound": r"\bultrasound(s)?\b",
        "ecg": r"\becg\b",
        "ekg": r"\bekg\b",
        "mri": r"\bmri\b",
        "ct scan": r"\bct scan(s)?\b",
        "blood work": r"\bblood work\b",
    }

    text_lower = text.lower()
    found_keywords: list[str] = []
    for keyword, pattern in keyword_patterns.items():
        if re.search(pattern, text_lower):
            found_keywords.append(keyword)

    # Preserve insertion order while removing duplicates.
    return list(dict.fromkeys(found_keywords))

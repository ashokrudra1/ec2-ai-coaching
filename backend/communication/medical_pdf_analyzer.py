"""
Medical PDF Upload & Analysis System
Handles PDF uploads from Telegram bot
Extracts medical parameters and updates athlete profile
"""
import logging
import os
import io
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models import User, MedicalReport
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


class MedicalPDFAnalyzer:
    """
    Analyzes medical reports and extracts key parameters
    """

    # Keywords to search for in extracted text
    PARAM_KEYWORDS = {
        "vo2max": ["vo2max", "vo2 max", "vo₂max", "maximum oxygen"],
        "lactate_threshold": ["lactate threshold", "threshold", "lthr", "lt", "anaerobic threshold"],
        "resting_hr": ["resting heart rate", "resting hr", "rest hr", "rhr"],
        "max_hr": ["maximum heart rate", "max heart rate", "max hr"],
        "blood_pressure": ["blood pressure", "bp", "/"],
        "cholesterol": ["cholesterol", "ldl", "hdl"],
        "bmI": ["bmi", "body mass"],
    }

    @staticmethod
    async def extract_text_from_pdf(file_path: str) -> str:
        """
        Extract text from PDF file
        Uses pytesseract for OCR if PyPDF2 extraction is insufficient
        """
        try:
            import PyPDF2

            extracted_text = ""

            with open(file_path, "rb") as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    extracted_text += page.extract_text()

            logger.info(f"✅ PDF text extracted: {len(extracted_text)} characters")

            # If text is too short, try OCR
            if len(extracted_text) < 100:
                logger.warning("⚠️ Text extraction insufficient, attempting OCR...")
                extracted_text = await MedicalPDFAnalyzer._ocr_pdf(file_path)

            return extracted_text

        except Exception as e:
            logger.error(f"❌ PDF extraction error: {e}")
            return ""

    @staticmethod
    async def _ocr_pdf(file_path: str) -> str:
        """
        Fallback: OCR using pytesseract
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(file_path)
            ocr_text = ""

            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                ocr_text += text
                logger.info(f"Page {i+1} OCR'd")

            return ocr_text

        except Exception as e:
            logger.error(f"❌ OCR error: {e}")
            return ""

    @staticmethod
    def parse_medical_data(text: str) -> Dict:
        """
        Parse extracted text and extract medical parameters
        """
        try:
            extracted_data = {}
            text_lower = text.lower()

            # VO2Max extraction
            vo2max = MedicalPDFAnalyzer._extract_vo2max(text_lower)
            if vo2max:
                extracted_data["vo2max"] = vo2max

            # Lactate Threshold
            lactate = MedicalPDFAnalyzer._extract_lactate_threshold(text_lower)
            if lactate:
                extracted_data["lactate_threshold"] = lactate

            # Resting HR
            rhr = MedicalPDFAnalyzer._extract_resting_hr(text_lower)
            if rhr:
                extracted_data["resting_hr"] = rhr

            # Blood Pressure
            bp = MedicalPDFAnalyzer._extract_blood_pressure(text_lower)
            if bp:
                extracted_data["blood_pressure"] = bp

            # Medical conditions/medications (text-based)
            medications = MedicalPDFAnalyzer._extract_medications(text)
            if medications:
                extracted_data["medications"] = medications

            extracted_data["confidence"] = MedicalPDFAnalyzer._calculate_confidence(extracted_data)

            logger.info(f"✅ Medical data parsed: {extracted_data}")

            return extracted_data

        except Exception as e:
            logger.error(f"❌ Medical data parsing error: {e}")
            return {}

    @staticmethod
    def _extract_vo2max(text: str) -> Optional[float]:
        """Extract VO2Max value (format: XX.X ml/kg/min or XX.X VO2Max)"""
        import re

        patterns = [
            r"vo2\s*max\s*[:\s=]+\s*(\d+\.?\d*)\s*(?:ml/kg/min)?",
            r"(\d+\.?\d*)\s*ml/kg/min",
            r"vo₂max\s*[:\s=]+\s*(\d+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if 20 <= value <= 100:  # Reasonable VO2Max range
                        return value
                except (ValueError, AttributeError):
                    continue

        return None

    @staticmethod
    def _extract_lactate_threshold(text: str) -> Optional[float]:
        """Extract Lactate Threshold (format: XXX bpm or XXX bpm HR)"""
        import re

        patterns = [
            r"(?:lactate\s*)?threshold\s*[:\s=]+\s*(\d+)\s*(?:bpm|hr)?",
            r"lthr\s*[:\s=]+\s*(\d+)\s*(?:bpm|hr)?",
            r"anaerobic threshold\s*[:\s=]+\s*(\d+)\s*(?:bpm|hr)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if 100 <= value <= 200:  # Reasonable HR threshold
                        return value
                except (ValueError, AttributeError):
                    continue

        return None

    @staticmethod
    def _extract_resting_hr(text: str) -> Optional[int]:
        """Extract Resting Heart Rate"""
        import re

        patterns = [
            r"resting\s*(?:heart\s*)?rate\s*[:\s=]+\s*(\d+)\s*(?:bpm)?",
            r"rhr\s*[:\s=]+\s*(\d+)\s*(?:bpm)?",
            r"rest\s*(?:heart\s*)?rate\s*[:\s=]+\s*(\d+)\s*(?:bpm)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = int(match.group(1))
                    if 40 <= value <= 100:  # Reasonable RHR range
                        return value
                except (ValueError, AttributeError):
                    continue

        return None

    @staticmethod
    def _extract_blood_pressure(text: str) -> Optional[str]:
        """Extract Blood Pressure (format: XXX/XX mmHg)"""
        import re

        pattern = r"(\d{2,3})\s*/\s*(\d{2})\s*(?:mmhg)?"
        match = re.search(pattern, text)

        if match:
            systolic = match.group(1)
            diastolic = match.group(2)

            try:
                sys_val = int(systolic)
                dia_val = int(diastolic)

                if 90 <= sys_val <= 200 and 50 <= dia_val <= 120:
                    return f"{systolic}/{diastolic} mmHg"
            except (ValueError, AttributeError):
                pass

        return None

    @staticmethod
    def _extract_medications(text: str) -> Optional[str]:
        """Extract medication list"""
        import re

        # Look for sections like "Medications:" or "Drugs:"
        med_patterns = [
            r"medications?:\s*(.+?)(?:\n\n|\n(?:[a-z]{2,}:)|$)",
            r"current\s+(?:medications?|drugs):\s*(.+?)(?:\n\n|\n(?:[a-z]{2,}:)|$)",
            r"prescriptions?:\s*(.+?)(?:\n\n|\n(?:[a-z]{2,}:)|$)",
        ]

        for pattern in med_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                meds = match.group(1).strip()
                if len(meds) > 5:  # Only if meaningful content
                    return meds[:500]  # Limit to 500 chars

        return None

    @staticmethod
    def _calculate_confidence(data: Dict) -> float:
        """
        Calculate extraction confidence (0-1)
        Based on number of parameters extracted
        """
        if not data:
            return 0.0

        # More parameters extracted = higher confidence
        param_count = len([v for v in data.values() if v])
        confidence = min(1.0, param_count / 5)  # Max confidence at 5 parameters

        return round(confidence, 2)


class MedicalReportProcessor:
    """
    Handles medical report upload, storage, and DB updates
    """

    @staticmethod
    async def process_telegram_upload(
        file_id: str, file_name: str, user_id: int, file_content: bytes
    ) -> Dict:
        """
        Process medical PDF upload from Telegram
        1. Store file securely
        2. Extract text
        3. Parse medical data
        4. Update user profile
        """
        db = SessionLocal()

        try:
            # Step 1: Save file
            file_path = await MedicalReportProcessor._save_file(file_id, file_name, file_content)

            # Step 2: Extract text from PDF
            pdf_text = await MedicalPDFAnalyzer.extract_text_from_pdf(file_path)

            if not pdf_text:
                return {
                    "success": False,
                    "error": "Could not extract text from PDF. Please ensure it's a valid medical report.",
                }

            # Step 3: Parse medical data
            extracted_data = MedicalPDFAnalyzer.parse_medical_data(pdf_text)

            # Step 4: Create medical report record
            report = MedicalReport(
                user_id=user_id,
                file_path=file_path,
                extracted_data=extracted_data,
                vo2max=extracted_data.get("vo2max"),
                lactate_threshold=extracted_data.get("lactate_threshold"),
                resting_hr=extracted_data.get("resting_hr"),
                blood_pressure=extracted_data.get("blood_pressure"),
                medications=extracted_data.get("medications"),
                uploaded_at=datetime.now(timezone.utc),
            )

            db.add(report)

            # Step 5: Update user profile with extracted data
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                if extracted_data.get("vo2max"):
                    user.physiological_twin["vo2max_estimate"] = extracted_data["vo2max"]

                if extracted_data.get("resting_hr"):
                    user.rest_hr = extracted_data["resting_hr"]

                if extracted_data.get("blood_pressure"):
                    user.medical_insights = extracted_data.get("blood_pressure")

                if extracted_data.get("medications"):
                    user.medical_insights = (
                        f"Medications: {extracted_data['medications']}\n"
                        f"Uploaded: {datetime.now(timezone.utc).isoformat()}"
                    )

            db.commit()

            logger.info(f"✅ Medical report processed for user {user_id}")

            return {
                "success": True,
                "message": f"Medical report analyzed! Found {extracted_data.get('confidence', 0)*100:.0f}% confidence metrics.",
                "extracted_data": extracted_data,
                "report_id": report.id,
            }

        except Exception as e:
            logger.error(f"❌ Medical report processing error: {e}", exc_info=True)
            db.rollback()
            return {"success": False, "error": f"Processing error: {str(e)}"}

        finally:
            db.close()

    @staticmethod
    async def _save_file(file_id: str, file_name: str, file_content: bytes) -> str:
        """
        Save uploaded file securely
        Uses encrypted storage or S3
        """
        try:
            # For now, save locally
            # TODO: Integrate S3 or encrypted storage
            upload_dir = "uploads/medical_reports"
            os.makedirs(upload_dir, exist_ok=True)

            file_path = os.path.join(upload_dir, f"{file_id}_{file_name}")

            with open(file_path, "wb") as f:
                f.write(file_content)

            logger.info(f"✅ File saved: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"❌ File save error: {e}")
            raise

    @staticmethod
    def get_user_medical_history(db: Session, user_id: int) -> Dict:
        """
        Retrieve user's medical report history
        """
        try:
            reports = (
                db.query(MedicalReport)
                .filter_by(user_id=user_id)
                .order_by(MedicalReport.uploaded_at.desc())
                .all()
            )

            history = []
            for report in reports:
                history.append(
                    {
                        "id": report.id,
                        "uploaded_at": report.uploaded_at.isoformat(),
                        "extracted_data": report.extracted_data,
                        "vo2max": report.vo2max,
                        "lactate_threshold": report.lactate_threshold,
                    }
                )

            return {"success": True, "history": history}

        except Exception as e:
            logger.error(f"❌ Medical history retrieval error: {e}")
            return {"success": False, "error": str(e)}

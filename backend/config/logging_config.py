# backend/config/logging_config.py
import json
import logging
import sys
from datetime import datetime, timezone

class StructuredJsonFormatter(logging.Formatter):
    def format(self, record):
        log_object = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "line_number": record.lineno,
        }
        
        # Capture optional dict variables passed to logger
        if isinstance(record.msg, dict):
            log_object.update(record.msg)
            
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_object, ensure_ascii=False)

def setup_production_logging():
    # Enforce UTF-8 output to prevent Unicode corruption in logs/terminal streams.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO, encoding="utf-8", force=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clean up standard default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(console_handler)

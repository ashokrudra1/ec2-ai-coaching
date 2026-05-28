"""
Phase 4 Webhook & External API Layer Tests
Tests TelegramWebhookHandler, StravaWebhookHandler, and OAuth flows
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.webhook import TelegramWebhookHandler, StravaWebhookHandler
from backend.pdf_utils import (
    extract_text_from_pdf_bytes,
    clean_extracted_text,
    validate_pdf_bytes,
    extract_medical_keywords
)


class TestTelegramWebhookHandler:
    """Tests for Telegram webhook handler"""
    
    def test_validate_secret_valid_token(self):
        """Test valid secret token validation"""
        with patch('backend.webhook.settings') as mock_settings:
            mock_settings.TELEGRAM_SECRET_TOKEN = "valid_token"
            assert TelegramWebhookHandler.validate_secret("valid_token") is True
    
    def test_validate_secret_invalid_token(self):
        """Test invalid secret token rejection"""
        with patch('backend.webhook.settings') as mock_settings:
            mock_settings.TELEGRAM_SECRET_TOKEN = "valid_token"
            assert TelegramWebhookHandler.validate_secret("invalid_token") is False
    
    def test_validate_secret_missing_token(self):
        """Test missing secret token rejection"""
        assert TelegramWebhookHandler.validate_secret(None) is False
        assert TelegramWebhookHandler.validate_secret("") is False
    
    def test_parse_message_text(self):
        """Test parsing text message"""
        body = {
            "message": {
                "text": "Hello bot",
                "chat": {"id": 123}
            }
        }
        is_valid, msg_type = TelegramWebhookHandler.parse_message(body)
        assert is_valid is True
        assert msg_type == "text"
    
    def test_parse_message_callback(self):
        """Test parsing callback query"""
        body = {
            "callback_query": {
                "data": "start_training",
                "message": {"chat": {"id": 123}}
            }
        }
        is_valid, msg_type = TelegramWebhookHandler.parse_message(body)
        assert is_valid is True
        assert msg_type == "callback"
    
    def test_parse_message_document(self):
        """Test parsing document upload"""
        body = {
            "message": {
                "document": {"file_id": "abc123", "mime_type": "application/pdf"},
                "chat": {"id": 123}
            }
        }
        is_valid, msg_type = TelegramWebhookHandler.parse_message(body)
        assert is_valid is True
        assert msg_type == "document"
    
    def test_parse_message_unknown(self):
        """Test parsing unknown message type"""
        body = {
            "message": {
                "photo": [{"file_id": "abc123"}],
                "chat": {"id": 123}
            }
        }
        is_valid, msg_type = TelegramWebhookHandler.parse_message(body)
        assert is_valid is False
        assert msg_type == "unknown"


class TestStravaWebhookHandler:
    """Tests for Strava webhook handler"""
    
    def test_validate_signature_valid(self):
        """Test valid Strava signature"""
        with patch('backend.strava_webhooks.settings') as mock_settings:
            mock_settings.STRAVA_SIGNING_SECRET = "secret"
            
            body = b'{"test": "data"}'
            expected_sig = hmac.new(
                b"secret",
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Import the function fresh since we patched settings
            from backend.strava_webhooks import validate_strava_signature
            result = validate_strava_signature(body, expected_sig)
            assert result is True
    
    def test_validate_signature_invalid(self):
        """Test invalid Strava signature"""
        with patch('backend.strava_webhooks.settings') as mock_settings:
            mock_settings.STRAVA_SIGNING_SECRET = "secret"
            
            body = b'{"test": "data"}'
            invalid_sig = "invalid_signature_here"
            
            from backend.strava_webhooks import validate_strava_signature
            result = validate_strava_signature(body, invalid_sig)
            assert result is False
    
    def test_validate_signature_missing(self):
        """Test missing signature"""
        with patch('backend.strava_webhooks.settings') as mock_settings:
            mock_settings.STRAVA_SIGNING_SECRET = "secret"
            
            from backend.strava_webhooks import validate_strava_signature
            result = validate_strava_signature(b'{}', "")
            assert result is False


class TestPDFUtils:
    """Tests for PDF extraction utilities"""
    
    def test_clean_extracted_text(self):
        """Test text cleaning"""
        messy_text = "Hello  \n\n\n  World  \t  Test"
        cleaned = clean_extracted_text(messy_text)
        
        # Should have single spaces and newlines
        assert "  " not in cleaned  # No double spaces
        assert "\n\n\n" not in cleaned  # No triple newlines
        assert cleaned == "Hello\nWorld\nTest"
    
    def test_validate_pdf_bytes_valid(self):
        """Test valid PDF validation"""
        # Minimal valid PDF structure
        valid_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\nendobj\nxref\ntrailer\nstartxref\neof"
        
        with patch('backend.pdf_utils.PdfReader') as mock_reader:
            mock_reader.return_value.pages = [MagicMock()]  # At least one page
            is_valid, msg = validate_pdf_bytes(valid_pdf)
            assert is_valid is True
            assert msg == ""
    
    def test_validate_pdf_bytes_invalid_header(self):
        """Test invalid PDF header"""
        invalid_pdf = b"NOTPDF content here"
        is_valid, msg = validate_pdf_bytes(invalid_pdf)
        assert is_valid is False
        assert "Invalid PDF header" in msg
    
    def test_validate_pdf_bytes_empty(self):
        """Test empty PDF bytes"""
        is_valid, msg = validate_pdf_bytes(b"")
        assert is_valid is False
        assert "Empty PDF content" in msg
    
    def test_extract_medical_keywords(self):
        """Test medical keyword extraction"""
        text = "Patient diagnosed with diabetes and hypertension. Blood pressure elevated."
        keywords = extract_medical_keywords(text)
        
        assert "patient" in keywords
        assert "diagnosis" in [k for k in keywords if k in text.lower()]
        assert "diabetes" in keywords
        assert "blood pressure" in keywords


class TestStravaAuthHelper:
    """Tests for Strava OAuth helpers"""
    
    def test_pkce_code_verifier_generation(self):
        """Test PKCE code verifier generation"""
        from backend.strava_auth import PKCEHelper
        
        verifier = PKCEHelper.generate_code_verifier()
        assert len(verifier) >= 43
        assert len(verifier) <= 128
        assert isinstance(verifier, str)
    
    def test_pkce_code_challenge_generation(self):
        """Test PKCE code challenge generation"""
        from backend.strava_auth import PKCEHelper
        
        verifier = PKCEHelper.generate_code_verifier()
        challenge = PKCEHelper.generate_code_challenge(verifier)
        
        assert isinstance(challenge, str)
        assert len(challenge) > 0
        assert challenge != verifier  # Challenge should be different from verifier
    
    def test_oauth_state_validation(self):
        """Test OAuth state validation"""
        from backend.strava_auth import validate_oauth_state
        
        chat_id = "12345"
        assert validate_oauth_state(chat_id, chat_id) is True
        assert validate_oauth_state("wrong", chat_id) is False
        assert validate_oauth_state(None, chat_id) is False
        assert validate_oauth_state("", chat_id) is False


class TestWebhookIntegration:
    """Integration tests for webhook endpoints"""
    
    @patch('backend.webhook.trigger_durable_webhook_handler')
    @patch('backend.webhook.settings')
    def test_telegram_webhook_endpoint_valid(self, mock_settings, mock_handler):
        """Test telegram webhook endpoint with valid request"""
        from backend.main import app
        
        mock_settings.TELEGRAM_SECRET_TOKEN = "test_secret"
        mock_settings.DEFAULT_RATE_LIMIT = "60 per minute"
        
        client = TestClient(app)
        
        payload = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "chat": {"id": 123, "type": "private"},
                "text": "Hello bot"
            }
        }
        
        response = client.post(
            "/webhook/telegram",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret"}
        )
        
        assert response.status_code == 200
        assert response.json()["ok"] is True
    
    @patch('backend.strava_webhooks.validate_strava_signature')
    @patch('backend.strava_webhooks.settings')
    def test_strava_webhook_endpoint_valid(self, mock_settings, mock_validate):
        """Test strava webhook endpoint with valid request"""
        from backend.main import app
        
        mock_settings.DEFAULT_RATE_LIMIT = "60 per minute"
        mock_validate.return_value = True
        
        client = TestClient(app)
        
        payload = {
            "object_type": "activity",
            "aspect_type": "create",
            "object_id": 12345,
            "owner_id": 67890,
            "subscription_id": 123,
            "event_time": 1234567890
        }
        
        response = client.post(
            "/webhook/strava",
            json=payload,
            headers={"X-Strava-Hook-Signature": "valid_sig"}
        )
        
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

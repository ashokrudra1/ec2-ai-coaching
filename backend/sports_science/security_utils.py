import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_byok_cipher() -> Fernet:
    key = os.getenv("STRAVA_BYOK_SECRET_KEY")
    if not key:
        logger.error("STRAVA_BYOK_SECRET_KEY is missing; BYOK crypto is unavailable")
        raise RuntimeError("BYOK encryption key is not configured")
    try:
        return Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        logger.error("STRAVA_BYOK_SECRET_KEY is malformed and cannot initialize Fernet")
        raise RuntimeError("Invalid BYOK encryption key format") from exc


def encrypt_client_secret(raw_secret: str) -> str:
    if not raw_secret:
        raise ValueError("raw_secret must be a non-empty string")
    cipher = _get_byok_cipher()
    encrypted_bytes = cipher.encrypt(raw_secret.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_client_secret(encrypted_secret: str) -> str:
    if not encrypted_secret:
        raise ValueError("encrypted_secret must be a non-empty string")
    cipher = _get_byok_cipher()
    try:
        decrypted_bytes = cipher.decrypt(encrypted_secret.encode("utf-8"))
    except InvalidToken as exc:
        logger.error("Unable to decrypt BYOK Strava client secret; token is invalid")
        raise ValueError("Invalid encrypted client secret payload") from exc
    return decrypted_bytes.decode("utf-8")

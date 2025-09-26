from cryptography.fernet import Fernet
import base64
import os
import structlog

logger = structlog.get_logger(__name__)

class EncryptionService:
    """Service for encrypting and decrypting sensitive data using Fernet (AES 128 + HMAC SHA256)"""

    def __init__(self):
        """Initialize encryption service with master key from environment"""
        key = os.getenv("ENCRYPTION_MASTER_KEY")
        if not key:
            raise ValueError("ENCRYPTION_MASTER_KEY environment variable is required")

        try:
            # Validate the key format
            self.cipher = Fernet(key.encode())
            logger.info("Encryption service initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize encryption service", error=str(e))
            raise ValueError(f"Invalid ENCRYPTION_MASTER_KEY format: {str(e)}")

    def encrypt(self, value: str) -> str:
        """
        Encrypt a string value

        Args:
            value: Plain text string to encrypt

        Returns:
            Base64 encoded encrypted string
        """
        if not value:
            return value

        try:
            encrypted_bytes = self.cipher.encrypt(value.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error("Failed to encrypt value", error=str(e))
            raise ValueError(f"Encryption failed: {str(e)}")

    def decrypt(self, encrypted_value: str) -> str:
        """
        Decrypt an encrypted string value

        Args:
            encrypted_value: Base64 encoded encrypted string

        Returns:
            Decrypted plain text string
        """
        if not encrypted_value:
            return encrypted_value

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_value.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error("Failed to decrypt value", error=str(e))
            raise ValueError(f"Decryption failed: {str(e)}")

    def is_encrypted_format(self, value: str) -> bool:
        """
        Check if a value appears to be in encrypted format (Fernet token)

        Args:
            value: String to check

        Returns:
            True if value appears to be encrypted, False otherwise
        """
        if not value:
            return False

        try:
            # Fernet tokens are base64 encoded and have a specific structure
            # They start with version info and are typically 128+ characters
            return len(value) > 100 and value.replace('-', '+').replace('_', '/').isalnum()
        except:
            return False

# Singleton instance for global use
encryption_service = EncryptionService()

def encrypt_sensitive_data(value: str) -> str:
    """Convenience function to encrypt sensitive data"""
    return encryption_service.encrypt(value)

def decrypt_sensitive_data(encrypted_value: str) -> str:
    """Convenience function to decrypt sensitive data"""
    return encryption_service.decrypt(encrypted_value)
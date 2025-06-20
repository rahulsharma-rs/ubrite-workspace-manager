from cryptography.fernet import Fernet
import base64
import os


def generate_key():
    """Generate a new encryption key."""
    return Fernet.generate_key()


def encrypt_data(data, key):
    """Encrypt data using the provided key."""
    if isinstance(data, str):
        data = data.encode('utf-8')

    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data)
    return encrypted_data


def decrypt_data(encrypted_data, key):
    """Decrypt data using the provided key."""
    fernet = Fernet(key)
    decrypted_data = fernet.decrypt(encrypted_data)
    return decrypted_data.decode('utf-8')


def generate_secure_token(length=32):
    """Generate a secure random token."""
    return base64.urlsafe_b64encode(os.urandom(length)).decode('utf-8')

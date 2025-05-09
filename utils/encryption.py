from cryptography.fernet import Fernet
import base64
import os

def generate_key():
    """Generate a new encryption key."""
    return Fernet.generate_key()

def encrypt_data(data, key):
    """Encrypt data using the provided key."""
    if isinstance(data, str):
        data = data.encode()
    f = Fernet(key)
    return f.encrypt(data)

def decrypt_data(encrypted_data, key):
    """Decrypt data using the provided key."""
    f = Fernet(key)
    decrypted_data = f.decrypt(encrypted_data)
    return decrypted_data.decode()

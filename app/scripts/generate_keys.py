# app/scripts/generate_keys.py
'''
EMAIL_PEPPER: rotation breaks lookups for existing email_hash values. If you must rotate, keep old pepper temporarily and try both old/new during a migration window, then re-hash and drop the old one.

FERNET_KEY: you can re-encrypt email_enc values to a new key during maintenance; keep both keys available during the rotation.

'''
from cryptography.fernet import Fernet
import os, base64

# Print a random HMAC key for EMAIL_PEPPER in .env. You can use either base64 or hex. Aim for 32–64 bytes of randomness.
print(f"Email Pepper: ", base64.urlsafe_b64encode(os.urandom(48)).decode())

# Run this once to generate a new Fernet key for .env
print(f"Fernet key: ", Fernet.generate_key().decode())


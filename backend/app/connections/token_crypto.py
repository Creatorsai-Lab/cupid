"""
Token Encryption — symmetric encryption for OAuth tokens at rest.

═══════════════════════════════════════════════════════════════════════════
WHY ENCRYPT?
═══════════════════════════════════════════════════════════════════════════
Access tokens grant access to user data on third-party platforms. If our
database is ever leaked, plaintext tokens become a credential leak across
every connected user. Encrypting them with a server-side key turns a
"dump all tokens" attack into "you have a wall of garbage."

The encryption key lives in an env variable, NEVER in the database.
An attacker would need both the DB AND the env file to decrypt.

═══════════════════════════════════════════════════════════════════════════
FERNET, BRIEFLY
═══════════════════════════════════════════════════════════════════════════
Fernet is a symmetric encryption recipe from the `cryptography` library:
    - AES-128 in CBC mode for the cipher
    - HMAC-SHA256 for authentication (prevents tampering)
    - Timestamp + version byte for crypto agility
    - URL-safe base64 output (storable in any string column)

It's the standard "I just want to encrypt some bytes safely" tool in
Python. Used by Django, Flask-AppBuilder, and basically every Python
service that encrypts at rest.

You don't need to understand AES/HMAC internals to use Fernet correctly.
You just need to:
    1. Generate the key once: Fernet.generate_key()
    2. Store the key as a secret (env var, secrets manager)
    3. Pass strings through encrypt() / decrypt()

═══════════════════════════════════════════════════════════════════════════
GENERATING YOUR KEY
═══════════════════════════════════════════════════════════════════════════
First time only — run this in a Python REPL once and save the output:

    >>> from cryptography.fernet import Fernet
    >>> Fernet.generate_key().decode()
    'jZdOh7K9mF2pXr...'  # something like this, 44 chars

Add it to your .env:
    TOKEN_ENCRYPTION_KEY=jZdOh7K9mF2pXr...

NEVER commit this key. NEVER change it after tokens are encrypted (you'd
lose ability to decrypt them — users would all need to reconnect).
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Get or create the Fernet instance. Cached so we don't reinitialize
    on every encrypt/decrypt call.

    Raises:
        ValueError if the key isn't set or is malformed.
    """
    key = settings.token_encryption_key
    if not key:
        raise ValueError(
            "TOKEN_ENCRYPTION_KEY not set. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and add it to .env"
        )

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"TOKEN_ENCRYPTION_KEY is malformed. Must be a Fernet-generated "
            f"44-char base64 key. Error: {exc}"
        )


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a plaintext token to a string suitable for DB storage.

    Args:
        plaintext: the raw access_token or refresh_token from OAuth

    Returns:
        A url-safe base64 string. Storable in TEXT or VARCHAR column.
    """
    if not plaintext:
        return ""

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypt a stored token back to its original form.

    Args:
        ciphertext: the encrypted string previously returned by encrypt_token()

    Returns:
        The original plaintext token.

    Raises:
        InvalidToken if the ciphertext is corrupt or the key is wrong.
        This usually means the encryption key was rotated — affected
        users need to reconnect their accounts.
    """
    if not ciphertext:
        return ""

    fernet = _get_fernet()
    try:
        plaintext_bytes = fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext_bytes.decode("utf-8")
    except InvalidToken:
        # Don't leak which key was used. Just signal "this is broken."
        raise InvalidToken(
            "Token decryption failed — the encryption key may have been "
            "rotated, or the stored value is corrupt."
        )
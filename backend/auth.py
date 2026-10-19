
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from pwdlib import PasswordHash
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "AUTH_SECRET_KEY is missing. Add a unique secret to backend/.env."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    user_id = payload.get("sub")
    if not user_id:
        raise jwt.InvalidTokenError("Missing user identifier")

    return user_id

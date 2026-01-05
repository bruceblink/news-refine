import datetime
from datetime import datetime, timedelta

from jose import jwt, JWTError

SECRET_KEY = "change_me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(user_id: int, org_id: int | None, role: str):
    payload = {
        "sub": str(user_id),
        "org_id": org_id,
        "role": role,
        "iat": datetime.now(datetime.UTC),
        "exp": datetime.now(datetime.UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
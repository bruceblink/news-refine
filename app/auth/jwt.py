import datetime
import os
from datetime import datetime, timedelta

from jose import jwt, JWTError

JWT_SECRET = os.getenv("JWT_SECRET") or "change_me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# TODO: 认证暂时关闭，待 BFF 层接入 Agora 认证后恢复
# _env = os.getenv("APP_ENV", "production")
# if _env == "production" and JWT_SECRET == "change_me":
#     raise RuntimeError(
#         "JWT_SECRET 未配置！生产环境必须通过环境变量 JWT_SECRET 设置安全密钥，"
#         "请勿使用默认值 'change_me'。"
#     )


def create_access_token(user_id: int, org_id: int | None, role: str):
    payload = {
        "sub": str(user_id),
        "org_id": org_id,
        "role": role,
        "iat": datetime.now(datetime.UTC),
        "exp": datetime.now(datetime.UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        return None
from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.jwt import SECRET_KEY, ALGORITHM


class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization")
        request.state.user = None

        if auth and auth.startswith("Bearer "):
            token = auth[7:]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                request.state.user = {
                    "user_id": int(payload["sub"]),
                    "org_id": payload.get("org_id"),
                    "role": payload.get("role"),
                }
            except JWTError:
                pass  # 不在这里抛异常

        return await call_next(request)

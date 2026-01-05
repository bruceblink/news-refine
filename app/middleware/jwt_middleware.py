from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.jwt import decode_jwt
from app.core.context import UserContext


class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization")
        request.state.user = None

        if auth and auth.startswith("Bearer "):
            token = auth[7:]
            payload = decode_jwt(token)

            if payload:
                request.state.user = UserContext(
                    user_id=int(payload["sub"]),
                    org_id=payload.get("org_id"),
                    role=payload.get("role"),
                )

        return await call_next(request)

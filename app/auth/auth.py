from fastapi import Request, HTTPException, status

from app.core.context import UserContext
from app.core.rbac import ROLE_PERMISSIONS


def require_permission(permission: str):
    def checker(request: Request) -> UserContext:
        user: UserContext | None = request.state.user

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        permissions = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return user

    return checker

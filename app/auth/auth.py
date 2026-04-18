from fastapi import Request, HTTPException, status

from app.core.context import UserContext
from app.core.rbac import ROLE_PERMISSIONS


def require_permission(permission: str):
    # TODO: 认证暂时关闭，待 BFF 层接入 Agora 认证后恢复
    def checker(request: Request) -> None:
        return None

    return checker

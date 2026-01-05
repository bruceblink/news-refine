from fastapi import Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer(auto_error=False)  # auto_error=False 允许没有 token 访问匿名接口

def swagger_auth(
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """
    这个依赖只用于 Swagger UI 展示 Authorization header。
    真正的 JWT 解析还是由中间件做。
    """
    return credentials.credentials if credentials else None

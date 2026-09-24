"""
Keycloak JWT middleware — validates Bearer tokens from Keycloak.
Currently a passthrough stub for Phase 1.
Full OIDC enforcement wired in Phase 2 when the Studio UI is live.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class KeycloakAuthMiddleware(BaseHTTPMiddleware):
    """
    Passthrough in Phase 1.
    Phase 2: validate Authorization: Bearer <token> against Keycloak JWKS.
    """
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)


# Export for use in main.py
keycloak_auth = KeycloakAuthMiddleware

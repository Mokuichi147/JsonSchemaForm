from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException, Request

from schemaform.config import Settings


class AuthProvider(Protocol):
    def require_admin(self, request: Request) -> None: ...


class NoAuthProvider:
    def require_admin(self, request: Request) -> None:
        return None


class LDAPAuthProvider:
    def require_admin(self, request: Request) -> None:
        raise HTTPException(status_code=501, detail="LDAP認証は未実装です")


def get_auth_provider(settings: Settings) -> AuthProvider:
    if settings.auth_mode == "ldap":
        return LDAPAuthProvider()
    return NoAuthProvider()

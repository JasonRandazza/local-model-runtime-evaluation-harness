from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


KEYCHAIN_SERVICE = "local.jrazz.lmre.omlx"
OSAURUS_KEYCHAIN_SERVICE = "local.jrazz.lmre.osaurus"
KEYCHAIN_ACCOUNT = "benchmark-harness"


class CredentialState(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    AUTH_FAILED = "AUTH_FAILED"


class CredentialError(RuntimeError):
    code = "credential_unavailable"


@dataclass(frozen=True, repr=False)
class Credential:
    _value: str

    def __post_init__(self) -> None:
        if not self._value:
            raise CredentialError("credential is unavailable")

    def __repr__(self) -> str:
        return "Credential(REDACTED)"

    def authorization_header(self) -> str:
        return f"Bearer {self._value}"

    def api_key(self) -> str:
        """Raw key for argv injection (never log or serialize this)."""
        return self._value

    def looks_like_osaurus_access_key(self) -> bool:
        """True when value has osk-v1.<payload>.<signature> shape (no secret logged)."""
        parts = self._value.split(".")
        return len(parts) == 3 and parts[0] == "osk-v1" and bool(parts[1]) and bool(parts[2])


class CredentialProvider(Protocol):
    def status(self) -> CredentialState: ...
    def get(self) -> Credential: ...


class FakeCredentialProvider:
    def __init__(self, credential: Credential | None, auth_failed: bool = False) -> None:
        self.credential = credential
        self.auth_failed = auth_failed

    def status(self) -> CredentialState:
        if self.auth_failed:
            return CredentialState.AUTH_FAILED
        return CredentialState.PRESENT if self.credential else CredentialState.MISSING

    def get(self) -> Credential:
        if self.status() is not CredentialState.PRESENT or self.credential is None:
            raise CredentialError("credential could not be retrieved")
        return self.credential


class KeychainCredentialProvider:
    """Reads one fixed Keychain item without logging command output or secret data."""

    def __init__(
        self,
        service: str = KEYCHAIN_SERVICE,
        account: str = KEYCHAIN_ACCOUNT,
    ) -> None:
        self.service = service
        self.account = account

    def status(self) -> CredentialState:
        try:
            self.get()
        except CredentialError:
            return CredentialState.MISSING
        return CredentialState.PRESENT

    def get(self) -> Credential:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", self.service,
             "-a", self.account, "-w"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        value = result.stdout.rstrip("\n")
        if result.returncode != 0 or not value:
            raise CredentialError("credential could not be retrieved")
        return Credential(value)

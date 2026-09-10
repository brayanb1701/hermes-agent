"""Fail-closed ownership contract and owner writer lock.

The contract is deliberately local state.  It is the first thing ownership-aware
entrypoints read, before they create directories, preprocess scripts, or spawn a
child process.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Iterator

CONTRACT_FILENAME = "vault-ownership.json"
LOCK_FILENAME = "owner.lock"
LOCK_TIMEOUT_SECONDS = 2.0
LOCK_POLL_SECONDS = 0.05

_REQUIRED = (
    "version",
    "hostname",
    "role",
    "owner_hostname",
    "hermes_home",
    "vault_path",
    "repo_path",
    "state_dir",
    "snapshot_root",
    "contribution_root",
    "repository",
    "remote",
    "branch",
    "maintenance_branch",
)
_PATH_FIELDS = (
    "hermes_home",
    "vault_path",
    "repo_path",
    "state_dir",
    "snapshot_root",
    "contribution_root",
)


class OwnershipError(RuntimeError):
    """A missing, malformed, or mismatched ownership contract."""


class OwnershipBusy(OwnershipError):
    """The bounded owner lock could not be acquired."""


def _requested_home(hermes_home: str | os.PathLike[str] | None) -> Path:
    raw = hermes_home if hermes_home is not None else os.environ.get("HERMES_HOME")
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".hermes").resolve()


def _fail(message: str) -> None:
    raise OwnershipError(message)


def _validate_contract(
    contract: Any,
    *,
    expected_home: Path | None = None,
    check_identity: bool = True,
) -> dict[str, Any]:
    if not isinstance(contract, dict):
        _fail("ownership contract must be a JSON object")
    missing = [key for key in _REQUIRED if key not in contract]
    if missing:
        _fail("ownership contract missing required field(s): " + ", ".join(missing))
    if contract.get("version") != 1:
        _fail("ownership contract version must be 1")
    role = contract.get("role")
    if role not in {"owner", "contributor"}:
        _fail("ownership contract role must be 'owner' or 'contributor'")

    normalized = dict(contract)
    for key in _PATH_FIELDS:
        value = contract.get(key)
        if not isinstance(value, str) or not value.strip():
            _fail(f"ownership contract field {key!r} must be a non-empty absolute path")
        path = Path(value).expanduser()
        if not path.is_absolute():
            _fail(f"ownership contract field {key!r} must be absolute")
        # The public mirror path is an atomic pointer, not its current target.
        normalized[key] = os.path.abspath(path) if key == "vault_path" else str(path.resolve())

    if expected_home is not None and Path(normalized["hermes_home"]) != expected_home:
        _fail(
            "ownership contract hermes_home does not match the requested profile: "
            f"{normalized['hermes_home']} != {expected_home}"
        )
    if Path(normalized["hermes_home"]) != Path(normalized["hermes_home"]).resolve():
        _fail("ownership contract hermes_home must resolve to itself")

    for key in ("hostname", "owner_hostname", "repository", "remote", "branch", "maintenance_branch"):
        if not isinstance(contract.get(key), str) or not contract[key].strip():
            _fail(f"ownership contract field {key!r} must be a non-empty string")

    for key in ("capture_source_chat_ids", "capture_allowed_user_ids"):
        if key in contract:
            value = contract[key]
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                _fail(f"ownership contract field {key!r} must be a list of strings")

    current_hostname = socket.gethostname()
    if check_identity and contract["hostname"] != current_hostname:
        _fail(
            "ownership contract hostname mismatch: "
            f"contract={contract['hostname']!r}, current={current_hostname!r}"
        )
    if role == "owner" and contract["hostname"] != contract["owner_hostname"]:
        _fail("owner contract hostname must equal owner_hostname")
    if role == "contributor" and contract["hostname"] == contract["owner_hostname"]:
        _fail("contributor contract cannot run on owner_hostname")

    active_profile = os.environ.get("HERMES_PROFILE", "").strip()
    if active_profile and active_profile not in {"default", "__default__"}:
        _fail(f"ownership guard only supports the default profile, not {active_profile!r}")
    home_parts = Path(normalized["hermes_home"]).parts
    if "profiles" in home_parts:
        _fail("ownership guard only supports the default Hermes profile")

    return normalized


def load_contract(hermes_home=None) -> dict:
    """Load and validate the local ownership contract for the active profile.

    Validation includes exact socket hostname and role/host consistency.  No
    directory is created by this function; callers can safely use it as their
    first side-effect boundary.
    """
    home = _requested_home(hermes_home)
    contract_path = home / CONTRACT_FILENAME
    try:
        raw = json.loads(contract_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OwnershipError(f"ownership contract not found: {contract_path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnershipError(f"cannot read ownership contract {contract_path}: {exc}") from exc
    return _validate_contract(raw, expected_home=home)


def require_owner(contract):
    """Require a validated contract for the owner host and return it."""
    normalized = _validate_contract(contract)
    if normalized["role"] != "owner":
        raise OwnershipError(
            f"owner operation refused for role {normalized['role']!r}; contributor is read/contribute-only"
        )
    if normalized["hostname"] != normalized["owner_hostname"]:
        raise OwnershipError("owner operation refused: hostname is not owner_hostname")
    return normalized


@contextlib.contextmanager
def owner_lock(contract) -> Iterator[Path]:
    """Hold the non-blocking bounded owner lock for the complete write lifecycle.

    Contract validation happens before ``state_dir`` is created.  The lock is a
    POSIX advisory lock and is held across gate execution, the Hermes child,
    validation, commit, and push; callers must not defer publication to another
    acquisition.
    """
    normalized = require_owner(contract)
    state_dir = Path(normalized["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / LOCK_FILENAME
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - the supported owner host is Linux
        raise OwnershipError("owner_lock requires a platform with fcntl.flock") from exc

    handle = lock_path.open("a+", encoding="utf-8")
    acquired = False
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise OwnershipBusy(f"owner lock is busy: {lock_path}")
                time.sleep(LOCK_POLL_SECONDS)
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()} hostname={normalized['hostname']}\n")
        handle.flush()
        yield lock_path
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


__all__ = ["load_contract", "require_owner", "owner_lock", "OwnershipError", "OwnershipBusy"]

#!/usr/bin/env python3
"""Owner cron transaction. Native scheduler remains the schedule/delivery owner.

Only execute pre-authorized scoped jobs here. Advisory locks and root routing
prevent accidents by cooperating same-user processes, not hostile shell access.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_ownership_common import OwnershipError, load_contract, owner_lock, require_owner


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise OwnershipError(f'Git operation failed: {args[0]}: {result.stderr.strip()}')
    return result.stdout.strip()


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes(path, data, *, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _atomic_write_json(path, value):
    _write_bytes(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OwnershipError(f'Invalid {label}: {path}') from exc
    if not isinstance(value, dict):
        raise OwnershipError(f'Invalid {label}: {path}')
    return value


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _marker_phase(path, marker, phase, **fields):
    updated = dict(marker, phase=phase, **fields)
    _atomic_write_json(path, updated)
    return updated


def _assert_no_symlink_components(path, anchor):
    path, anchor = Path(path), Path(anchor)
    try:
        relative = path.relative_to(anchor)
    except ValueError as exc:
        raise OwnershipError(f'Path escapes ownership state: {path}') from exc
    current = anchor
    if current.is_symlink():
        raise OwnershipError(f'Symlink path component refused: {current}')
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise OwnershipError(f'Symlink path component refused: {current}')


def _worktree_heads(repo):
    fields = git(repo, 'worktree', 'list', '--porcelain', '-z').split('\0')
    worktrees = {}
    current = None
    for field in fields:
        if field.startswith('worktree '):
            current = field.removeprefix('worktree ')
            worktrees[current] = None
        elif current is not None and field.startswith('HEAD '):
            worktrees[current] = field.removeprefix('HEAD ')
    return worktrees


def _root_aware_processes(root, worker_identity=None, *, not_before):
    import psutil

    root = Path(root)
    uid = os.getuid()
    if not isinstance(not_before, (int, float)) or isinstance(not_before, bool) or not_before <= 0:
        raise OwnershipError('Process scan boundary is malformed')
    worker_pid = worker_identity and worker_identity.get('pid')
    worker_created = worker_identity and worker_identity.get('created')
    if (type(worker_pid) is int and worker_pid > 0
            and isinstance(worker_created, (int, float))
            and not isinstance(worker_created, bool) and worker_created > 0):
        try:
            worker = psutil.Process(worker_pid)
            same_process = abs(worker.create_time() - float(worker_created)) < 0.01
            if (same_process and worker.status() not in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}
                    and worker.is_running()):
                raise OwnershipError('Recorded native worker is still alive')
        except psutil.NoSuchProcess:
            pass
        except OwnershipError:
            raise
        except (psutil.Error, OSError) as exc:
            raise OwnershipError('Unable to verify recorded native worker identity') from exc
    elif worker_identity is not None:
        raise OwnershipError('Recorded native worker identity is malformed')

    def under(candidate):
        try:
            return candidate == root or root in candidate.parents
        except (OSError, RuntimeError):
            return False

    matches = []
    try:
        processes = list(psutil.process_iter(['pid', 'uids']))
    except psutil.Error as exc:
        raise OwnershipError('Unable to enumerate same-user processes') from exc
    for process in processes:
        try:
            uids = process.uids()
            if uids.real != uid or process.pid == os.getpid():
                continue
            created = process.create_time()
            if process.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                continue
        except psutil.NoSuchProcess:
            continue
        except (psutil.Error, OSError) as exc:
            raise OwnershipError('Unable to identify a same-user process') from exc
        preexisting = created + 1.0 < not_before
        cwd = argv = None
        access_errors = []
        try:
            cwd = Path(process.cwd())
        except psutil.NoSuchProcess:
            continue
        except (psutil.Error, OSError) as exc:
            access_errors.append(exc)
        try:
            argv = process.cmdline()
        except psutil.NoSuchProcess:
            continue
        except (psutil.Error, OSError) as exc:
            access_errors.append(exc)

        rooted = cwd is not None and under(cwd)
        if argv is not None:
            for token in argv:
                candidate = token.split('=', 1)[-1] if '=' in token else token
                if candidate.startswith('/') and under(Path(candidate)):
                    rooted = True
                    break
        if rooted:
            matches.append(process.pid)
        elif access_errors and not preexisting:
            # A process created during this owner run is a possible escaped
            # descendant; missing either identity surface is a hard refusal.
            raise OwnershipError('Unable to fully inspect a candidate same-user process')
    if matches:
        raise OwnershipError(f'Processes still reference failed worktree: {matches}')


def _validate_receipt(run_dir, *, legacy):
    receipt = _read_json(Path(run_dir) / 'result.json', 'native completion receipt')
    if type(receipt.get('success')) is not bool:
        raise OwnershipError('Completion receipt success flag is malformed')
    cleanup = receipt.get('descendant_cleanup')
    if not isinstance(cleanup, dict):
        raise OwnershipError('Completion receipt lacks containment evidence')
    survivors = cleanup.get('survivor_count')
    live_count = cleanup.get('live_count')
    if (type(survivors) is not int or survivors != 0
            or type(live_count) is not int or live_count < 0
            or cleanup.get('survivors') != []
            or not isinstance(cleanup.get('observed'), list)
            or 'cleanup_error' in cleanup):
        raise OwnershipError('Completion receipt does not prove zero-survivor containment')
    kernel_cleanup = receipt.get('kernel_cleanup')
    if kernel_cleanup is None and legacy:
        return receipt
    if (not isinstance(kernel_cleanup, dict)
            or set(kernel_cleanup) != {'local', 'remote'}
            or any(value != 'ok' for value in kernel_cleanup.values())):
        raise OwnershipError('Completion receipt does not prove successful kernel cleanup')
    return receipt


def _path_birth_time(path):
    result = subprocess.run(
        ['stat', '--format=%W', '--', str(path)], text=True, capture_output=True
    )
    if result.returncode:
        raise OwnershipError(f'Unable to read worktree creation boundary: {path}')
    try:
        created = int(result.stdout.strip())
    except ValueError as exc:
        raise OwnershipError(f'Invalid worktree creation boundary: {path}') from exc
    if created <= 0:
        raise OwnershipError(f'Worktree creation boundary is unavailable: {path}')
    return float(created)


def _validate_pending(contract, marker, expected_run=None, *, legacy=False):
    state = Path(contract['state_dir'])
    if legacy:
        if set(marker) != {'job', 'root', 'run', 'base'}:
            raise OwnershipError('Legacy owner marker schema is unknown')
        if not isinstance(marker.get('run'), str) or not isinstance(marker.get('root'), str):
            raise OwnershipError('Legacy owner marker paths are malformed')
        run_dir = Path(marker['run'])
        run_id = run_dir.name
        phase = 'legacy'
        worker_identity = None
        not_before = None
    else:
        required = {'version', 'kind', 'job', 'run', 'run_dir', 'root', 'base', 'intent',
                    'phase', 'pid', 'pid_created', 'started'}
        allowed = required | {'head', 'remote_head'}
        if (not required <= set(marker) or not set(marker) <= allowed
                or marker.get('version') != 1 or marker.get('kind') != 'owner-job'):
            raise OwnershipError('Pending marker is not a recognized owner-job record')
        if not isinstance(marker.get('run_dir'), str) or not isinstance(marker.get('root'), str):
            raise OwnershipError('Owner-job marker paths are malformed')
        run_id = marker['run']
        run_dir = Path(marker['run_dir'])
        phase = marker['phase']
        worker_identity = {'pid': marker['pid'], 'created': marker['pid_created']}
        try:
            started = datetime.fromisoformat(marker['started'])
            if started.tzinfo is None or started.utcoffset() is None:
                raise ValueError('timezone required')
            not_before = started.timestamp()
        except (TypeError, ValueError, OverflowError) as exc:
            raise OwnershipError('Owner-job start boundary is malformed') from exc
        intent = marker['intent']
        if (not isinstance(intent, dict) or set(intent) != {'name', 'allowed_paths'}
                or not isinstance(intent.get('name'), str) or not intent['name'].strip()):
            raise OwnershipError('Owner-job intent is malformed')
        validate_allowed_paths(intent['allowed_paths'])
    job_id = marker.get('job')
    root_value = marker.get('root')
    if not isinstance(root_value, str):
        raise OwnershipError('Pending marker root is malformed')
    root, base = Path(root_value), marker.get('base')
    if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id):
        raise OwnershipError('Pending marker run identifier is malformed')
    if expected_run is not None and run_id != expected_run:
        raise OwnershipError('Pending marker does not match requested run')
    if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', job_id):
        raise OwnershipError('Pending marker job identifier is malformed')
    if not isinstance(base, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
        raise OwnershipError('Pending marker base is malformed')
    expected_root = state / 'worktrees' / job_id / run_id
    expected_run_dir = state / 'runs' / run_id
    if root != expected_root or run_dir != expected_run_dir:
        raise OwnershipError('Pending marker paths do not match the recorded run identity')
    _assert_no_symlink_components(root, state)
    _assert_no_symlink_components(run_dir, state)
    birth_time = _path_birth_time(root)
    if legacy:
        not_before = birth_time
    elif (not isinstance(not_before, (int, float)) or isinstance(not_before, bool)
          or not_before > birth_time + 1.0
          or not_before > datetime.now(timezone.utc).timestamp() + 1.0):
        raise OwnershipError('Owner-job start boundary is inconsistent with the worktree')
    if not isinstance(phase, str):
        raise OwnershipError('Owner-job phase is malformed')
    known_phases = {'prepared', 'executing', 'validating', 'committing', 'publishing', 'integrating'}
    if not legacy and phase not in known_phases:
        raise OwnershipError(f'Owner-job phase {phase!r} is unknown')
    if not legacy:
        has_head, has_remote = 'head' in marker, 'remote_head' in marker
        if phase in {'prepared', 'executing', 'validating', 'committing'} and (has_head or has_remote):
            raise OwnershipError(f'Owner-job phase {phase!r} has impossible publication fields')
        if phase == 'publishing' and (not has_head or has_remote):
            raise OwnershipError('Publishing marker boundary is malformed')
        if phase == 'integrating' and (not has_head or not has_remote
                or marker['head'] != marker['remote_head']):
            raise OwnershipError('Integrating marker boundary is malformed')
    return run_id, job_id, root, run_dir, base, worker_identity, phase, not_before


def _changed_entries(root):
    staged = set(filter(None, git(root, 'diff', '--cached', '--name-only', '-z', 'HEAD').split('\0')))
    unstaged = set(filter(None, git(root, 'diff', '--name-only', '-z').split('\0')))
    untracked = set(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')))
    entries = []
    for name in sorted(staged | unstaged | untracked):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise OwnershipError(f'Unsafe changed path: {name}')
        source = Path(root) / relative
        _assert_no_symlink_components(source, root)
        status = 'present' if source.exists() else 'deleted'
        if status != 'deleted' and not source.is_file():
            raise OwnershipError(f'Changed path is not a regular file: {name}')
        digest = _sha256(source.read_bytes()) if status != 'deleted' else None
        entries.append({
            'path': name,
            'status': status,
            'staged': name in staged,
            'unstaged': name in unstaged,
            'untracked': name in untracked,
            'sha256': digest,
        })
    return entries


def _archive_material(root, run_dir, marker_path):
    entries = _changed_entries(root)
    cached_diff = subprocess.run(
        ['git', 'diff', '--cached', '--binary', 'HEAD'], cwd=root, check=True, capture_output=True
    ).stdout
    working_diff = subprocess.run(
        ['git', 'diff', '--binary'], cwd=root, check=True, capture_output=True
    ).stdout
    artifacts = {
        'tracked.cached.diff': cached_diff,
        'tracked.working.diff': working_diff,
        'records/pending-owner.original.json': marker_path.read_bytes(),
    }
    for entry in entries:
        if entry['status'] != 'deleted':
            artifacts[f"files/{entry['path']}"] = (root / entry['path']).read_bytes()
    for source in sorted(run_dir.rglob('*')):
        _assert_no_symlink_components(source, run_dir)
        if source.is_dir():
            continue
        if not source.is_file():
            raise OwnershipError(f'Run evidence is not a regular file: {source}')
        relative = source.relative_to(run_dir)
        if relative.is_absolute() or '..' in relative.parts:
            raise OwnershipError(f'Unsafe run evidence path: {relative}')
        artifacts[f'records/run/{relative}'] = source.read_bytes()
    return entries, artifacts


def _safe_archive_artifact(archive, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or name in {'', '.'}:
        raise OwnershipError(f'Unsafe failed-run artifact path: {name}')
    path = archive / relative
    _assert_no_symlink_components(path, archive)
    return path


def _archive_snapshot(state, marker_path, marker, run_id, root, run_dir, base):
    failed = state / 'failed'
    _assert_no_symlink_components(failed, state)
    failed.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(failed, state)
    archive = failed / run_id
    _assert_no_symlink_components(archive, state)
    entries, material = _archive_material(root, run_dir, marker_path)
    expected_hashes = {name: _sha256(data) for name, data in material.items()}

    if archive.exists():
        _assert_no_symlink_components(archive, state)
        manifest = _read_json(archive / 'manifest.json', 'failed-run manifest')
        if (manifest.get('complete') is not True or manifest.get('run') != run_id
                or manifest.get('base') != base or manifest.get('root') != str(root)
                or manifest.get('entries') != entries
                or manifest.get('artifacts') != expected_hashes):
            raise OwnershipError('Existing failed-run archive is incomplete, corrupt, or stale')
        for name, digest in expected_hashes.items():
            artifact = _safe_archive_artifact(archive, name)
            if not artifact.is_file() or _sha256(artifact.read_bytes()) != digest:
                raise OwnershipError(f'Failed-run archive artifact is corrupt: {name}')
        actual_files = set()
        for artifact in archive.rglob('*'):
            _assert_no_symlink_components(artifact, archive)
            if artifact.is_dir():
                continue
            if not artifact.is_file():
                raise OwnershipError(f'Failed-run archive contains unsafe artifact: {artifact}')
            relative = str(artifact.relative_to(archive))
            _safe_archive_artifact(archive, relative)
            actual_files.add(relative)
        if actual_files != set(expected_hashes) | {'manifest.json'}:
            raise OwnershipError('Failed-run archive artifact set is incomplete or unexpected')
        return archive

    temporary = failed / f'.{run_id}.{uuid.uuid4().hex}.tmp'
    _assert_no_symlink_components(temporary, state)
    temporary.mkdir()
    try:
        for name, data in material.items():
            destination = _safe_archive_artifact(temporary, name)
            _write_bytes(destination, data)
            if _sha256(data) != expected_hashes[name]:
                raise OwnershipError(f'Archive source mutated while copying: {name}')
        # Re-read every source after copying so changes between enumeration and completion fail closed.
        current_entries, current_material = _archive_material(root, run_dir, marker_path)
        if current_entries != entries or {
            name: _sha256(data) for name, data in current_material.items()
        } != expected_hashes:
            raise OwnershipError('Failed-run evidence mutated while archiving')
        manifest = {
            'version': 1, 'kind': 'failed-owner-job', 'complete': True,
            'run': run_id, 'root': str(root), 'base': base,
            'entries': entries, 'artifacts': expected_hashes,
        }
        _atomic_write_json(temporary / 'manifest.json', manifest)
        os.replace(temporary, archive)
        _fsync_directory(failed)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return archive


def _reconcile_locked(contract, *, expected_run=None, legacy=False):
    state, repo = Path(contract['state_dir']), Path(contract['repo_path'])
    marker_path = state / 'pending-owner.json'
    if marker_path.is_symlink():
        raise OwnershipError(f'Active pending-owner marker symlink refused: {marker_path}')
    if not marker_path.exists():
        return {'status': 'no-pending-owner'}
    marker = _read_json(marker_path, 'pending owner marker')
    run_id, _job, root, run_dir, base, worker_identity, phase, not_before = _validate_pending(
        contract, marker, expected_run, legacy=legacy
    )
    if not legacy and phase not in {'prepared', 'executing', 'validating'}:
        recorded_head = marker.get('head')
        if phase in {'publishing', 'integrating'} and (
                not isinstance(recorded_head, str)
                or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', recorded_head)):
            raise OwnershipError(f'Owner-job phase {phase!r} lacks a valid recorded publication head')
        advertised = git(
            repo, 'ls-remote', contract['remote'], f"refs/heads/{contract['branch']}"
        ).split()
        remote_head = advertised[0] if advertised else 'missing'
        raise OwnershipError(
            f'Owner-job phase {phase!r} is not safe to reconcile; '
            f'recorded_head={recorded_head or "none"} remote_head={remote_head}'
        )
    _validate_receipt(run_dir, legacy=legacy)
    _root_aware_processes(root, worker_identity, not_before=not_before)
    if git(repo, 'status', '--porcelain=v1', '-uall'):
        raise OwnershipError('Canonical checkout is dirty during reconciliation')
    if git(repo, 'rev-parse', 'HEAD') != base:
        raise OwnershipError('Canonical checkout changed since failed run')
    remote = git(repo, 'ls-remote', contract['remote'], f"refs/heads/{contract['branch']}").split()
    if not remote or remote[0] != base:
        raise OwnershipError('Published branch changed since failed run')
    if not root.is_dir() or git(root, 'rev-parse', 'HEAD') != base:
        raise OwnershipError('Failed worktree identity differs from recorded base')
    worktrees = _worktree_heads(repo)
    if worktrees.get(str(root)) != base:
        raise OwnershipError('Failed root is not the recorded Git worktree')
    archive = _archive_snapshot(state, marker_path, marker, run_id, root, run_dir, base)
    os.replace(marker_path, archive / 'pending-owner.json')
    _fsync_directory(archive)
    _fsync_directory(state)
    return {'status': 'archived', 'run': run_id, 'phase': phase, 'archive': str(archive)}


def reconcile_pending(contract, run_id=None, *, legacy=False):
    require_owner(contract)
    if run_id is not None and not re.fullmatch(r'[0-9a-f]{32}', run_id):
        raise OwnershipError('Requested reconciliation run identifier is malformed')
    with owner_lock(contract):
        return _reconcile_locked(contract, expected_run=run_id, legacy=legacy)


def audit_script_for_background_escape(path):
    """Inventory launch sites; source inspection is not a sandbox."""
    if Path(path).suffix != '.py':
        return ['Non-Python gate requires explicit lifecycle audit']
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    return [f'{node.lineno}: {ast.unparse(node.func)} requires lifecycle audit'
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {'Popen', 'fork', 'forkpty', 'posix_spawn', 'system'}]


def validate_allowed_paths(allowed_paths):
    if not isinstance(allowed_paths, list) or not allowed_paths or any(not isinstance(p, str) or p.startswith('/') or '..' in Path(p).parts
                                or p in {'', '.', '*', '**'} for p in allowed_paths):
        raise OwnershipError('Explicit relative allowed_paths are required')


def validate_diff(root, allowed_paths):
    validate_allowed_paths(allowed_paths)
    git(root, 'add', '--all')
    names = git(root, 'diff', '--cached', '--name-only', '-z').split('\0')
    for name in filter(None, names):
        if not any(name == p.rstrip('/') or (p.endswith('/') and name.startswith(p)) for p in allowed_paths):
            raise OwnershipError(f'Out-of-scope change: {name}')
        path = Path(root) / name
        if path.is_symlink():
            raise OwnershipError(f'Symlink output refused: {name}')
    # Markdown hard breaks and verbatim captured whitespace are valid content.
    return list(filter(None, names))


def publish(root, contract, base):
    """Exact-base CAS, but only after proving this is a fast-forward update."""
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
        raise OwnershipError('Publication requires an exact base SHA')
    head = git(root, 'rev-parse', 'HEAD')
    git(root, 'merge-base', '--is-ancestor', base, head)
    ref = f"refs/heads/{contract['branch']}"
    git(root, 'push', f'--force-with-lease={ref}:{base}', contract['remote'], f'{head}:{ref}')
    actual = git(root, 'ls-remote', contract['remote'], ref).split()[0]
    if actual != head:
        raise OwnershipError('Published head could not be verified')
    return head


def _descendant_record(process):
    """Return bounded, non-secret identity evidence for one descendant."""
    import psutil

    record = {"pid": process.pid, "ppid": None, "status": "unknown",
              "executable": "unknown", "start_time": None}
    with contextlib.suppress(psutil.Error, OSError):
        record["ppid"] = process.ppid()
    with contextlib.suppress(psutil.Error, OSError):
        record["status"] = process.status()
    with contextlib.suppress(psutil.Error, OSError):
        record["executable"] = Path(process.exe()).name or "unknown"
    if record["executable"] == "unknown":
        with contextlib.suppress(psutil.Error, OSError):
            record["executable"] = Path(process.name()).name or "unknown"
    with contextlib.suppress(psutil.Error, OSError):
        record["start_time"] = process.create_time()
    return record


def cleanup_native_descendants(descendants=None):
    """Reap inert zombies; kill and report every genuinely live descendant."""
    import psutil

    processes = list(descendants if descendants is not None
                     else psutil.Process().children(recursive=True))
    observed = [_descendant_record(process) for process in processes]
    live = []
    for process, record in zip(processes, observed):
        if record["status"] in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
            if record["ppid"] == os.getpid():
                with contextlib.suppress(ChildProcessError, ProcessLookupError, OSError):
                    os.waitpid(process.pid, os.WNOHANG)
            continue
        try:
            if process.is_running():
                live.append(process)
        except psutil.NoSuchProcess:
            continue
        except psutil.Error:
            # Unknown liveness is not permission to publish.
            live.append(process)
    for process in reversed(live):
        with contextlib.suppress(psutil.NoSuchProcess):
            process.kill()
    _, alive = psutil.wait_procs(live, timeout=5)
    survivors = [_descendant_record(process) for process in alive]
    return {"observed": observed, "live_count": len(live),
            "survivor_count": len(survivors), "survivors": survivors}


def _shutdown_native_kernels():
    """Dispose this dedicated worker's process-global local and remote kernels."""
    cleanup = {}
    disposers = (
        ("local", "tools.code_kernel", "shutdown_all_kernels"),
        ("remote", "tools.code_kernel_remote", "shutdown_all_remote_kernels"),
    )
    for kind, module_name, function_name in disposers:
        try:
            module = __import__(module_name, fromlist=[function_name])
            getattr(module, function_name)()
            cleanup[kind] = "ok"
        except Exception as exc:
            cleanup[kind] = type(exc).__name__
    return cleanup


def _native_worker(payload, receipt):
    """Run the ORIGINAL native job, including native wake gate and teardown."""
    import ctypes
    # Linux subreaper adopts double-fork/setsid workers when their gate exits.
    # This is scoped to the dedicated native worker, never the gateway process.
    if sys.platform != 'linux' or ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0):
        raise OwnershipError('Managed lifecycle requires Linux child subreaper support')
    from cron.scheduler import run_job
    job = json.loads(Path(payload).read_text(encoding='utf-8'))
    success, document, response, error = False, "", "", None
    run_exception = None
    run_traceback = None
    try:
        try:
            success, document, response, error = run_job(job)
        except BaseException as exc:
            run_exception = exc
            run_traceback = exc.__traceback__
    finally:
        kernel_cleanup = _shutdown_native_kernels()
        try:
            cleanup = cleanup_native_descendants()
        except Exception as exc:
            cleanup = {"observed": [], "live_count": None,
                       "survivor_count": None, "survivors": [],
                       "cleanup_error": type(exc).__name__}
    if cleanup["observed"]:
        print("Native descendant cleanup: " + json.dumps(cleanup, sort_keys=True), file=sys.stderr)
    if run_exception is not None:
        error = f"Native run raised {type(run_exception).__name__}"
    elif (any(value != "ok" for value in kernel_cleanup.values())
          or cleanup.get("cleanup_error") or cleanup["survivor_count"]):
        success, error = False, 'Unable to stop all native job descendants'
    elif cleanup["live_count"]:
        success, error = False, 'Native job left background descendants; stopped before publication'
    _atomic_write_json(Path(receipt), dict(success=success, document=document,
                                          response=response, error=error,
                                          kernel_cleanup=kernel_cleanup,
                                          descendant_cleanup=cleanup))
    if run_exception is not None:
        raise run_exception.with_traceback(run_traceback)
    return 0 if success else 1


def native_execute(job, root, run_dir):
    payload, receipt = run_dir / 'job.json', run_dir / 'result.json'
    payload.write_text(json.dumps(job))
    env = dict(os.environ, HERMES_VAULT_ROOT=str(root))
    # Source checkout explicitly configured at deployment; no provider changes.
    source = load_contract()['hermes_source']
    env['PYTHONPATH'] = str(source) + os.pathsep + env.get('PYTHONPATH', '')
    with (run_dir / 'native.log').open('w') as output:
        proc = subprocess.Popen([sys.executable, __file__, '--native', str(payload), str(receipt)],
                                cwd=root, env=env, stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            import psutil
            pending = run_dir.parent.parent / 'pending-owner.json'
            marker = _read_json(pending, 'pending owner marker')
            _marker_phase(pending, marker, marker['phase'], pid=proc.pid,
                          pid_created=psutil.Process(proc.pid).create_time())
            proc.wait(timeout=job.get('ownership_timeout', 600))
        except BaseException:
            import psutil
            children = psutil.Process(proc.pid).children(recursive=True)
            for child in children:
                with contextlib.suppress(psutil.NoSuchProcess):
                    child.kill()
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise
    if not receipt.exists():
        raise OwnershipError('Native job exited without a completion receipt')
    result = json.loads(receipt.read_text())
    if proc.returncode or not result['success']:
        raise OwnershipError(result.get('error') or 'Native job failed')
    return result['response']


def require_writable_canonical(root):
    # Only contributor snapshots are chmod-readonly. The canonical owner checkout
    # stays writable for native intake and verified fast-forward integration.
    import stat
    root = Path(root)
    if not root.is_dir() or not root.stat().st_mode & stat.S_IWUSR or not os.access(root, os.W_OK):
        raise OwnershipError('Canonical owner checkout must remain writable; only contributor snapshots are read-only')


def execute_job(contract, job, *, executor=native_execute):
    require_owner(contract)
    validate_allowed_paths(job.get('allowed_paths'))
    job_id = job['id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', job_id):
        raise OwnershipError('Invalid job identifier')
    state, repo = Path(contract['state_dir']), Path(contract['repo_path'])
    require_writable_canonical(repo)
    with owner_lock(contract):
        pending = state / 'pending-owner.json'
        if pending.is_symlink():
            raise OwnershipError(f'Active pending-owner marker symlink refused: {pending}')
        if pending.exists():
            _reconcile_locked(contract)
        if git(repo, 'status', '--porcelain'):
            raise OwnershipError('Canonical checkout is dirty; refusing to sweep unrelated work')
        branch, remote = contract['branch'], contract['remote']
        git(repo, 'fetch', '--no-tags', remote, branch)
        base = git(repo, 'rev-parse', 'FETCH_HEAD')
        if git(repo, 'rev-parse', 'HEAD') != base:
            raise OwnershipError('Canonical checkout differs from published base')
        run_id = uuid.uuid4().hex
        root = state / 'worktrees' / job_id / run_id
        run_dir = state / 'runs' / run_id
        run_dir.mkdir(parents=True)
        root.parent.mkdir(parents=True, exist_ok=True)
        marker = {
            'version': 1,
            'kind': 'owner-job',
            'job': job_id,
            'run': run_id,
            'run_dir': str(run_dir),
            'root': str(root),
            'base': base,
            'pid': None,
            'pid_created': None,
            'started': datetime.now(timezone.utc).isoformat(),
            'intent': {
                'name': str(job.get('name') or job_id),
                'allowed_paths': list(job['allowed_paths']),
            },
            'phase': 'prepared',
        }
        _atomic_write_json(pending, marker)
        git(repo, 'worktree', 'add', '--detach', str(root), base)
        marker = _marker_phase(pending, marker, 'executing')
        routed = dict(job, workdir=str(root))
        # Native job fields (models, tools, skills, prompts, gate, context) survive.
        routed['prompt'] = (job.get('prompt') or '') + (
            f'\nOwnership execution root: {root}. This is the ONLY writable vault for this run. '
            'Resolve every vault path, script and descendant against HERMES_VAULT_ROOT. '
            'Canonical/read snapshots are read-only. Do not publish or leave background workers.')
        try:
            response = executor(routed, root, run_dir)
            marker = _read_json(pending, 'pending owner marker')
            marker = _marker_phase(pending, marker, 'validating')
            if git(root, 'rev-parse', 'HEAD') != base:
                raise OwnershipError('Managed agent changed HEAD; preserve for recovery')
            names = validate_diff(root, job.get('allowed_paths'))
        except BaseException:
            try:
                _reconcile_locked(contract, expected_run=run_id)
            except Exception as recovery_error:
                print(f'Failed run retained for explicit reconciliation: {recovery_error}', file=sys.stderr)
            raise
        if names:
            marker = _marker_phase(pending, marker, 'committing')
            git(root, 'commit', '-m', f"Managed vault job {job_id}\n\nVault-Ownership-Job: {job_id}\n"
                f"Source-Host: {contract['hostname']}\nSession: {run_id}\nBase-SHA: {base}")
            head = git(root, 'rev-parse', 'HEAD')
            marker = _marker_phase(pending, marker, 'publishing', head=head)
            published = publish(root, contract, base)
            marker = _marker_phase(pending, marker, 'integrating', head=published,
                                   remote_head=published)
            git(repo, 'merge', '--ff-only', published)
        pending.unlink()  # Verified publication/no-change success precedes housekeeping.
        _fsync_directory(state)
        try:
            git(repo, 'worktree', 'remove', str(root))
        except OwnershipError as exc:
            print(f'Published run retained for cleanup: {root}: {exc}', file=sys.stderr)
        with contextlib.suppress(OSError):
            root.parent.rmdir()
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id', nargs='?')
    parser.add_argument('--native', nargs=2, metavar=('JOB', 'RECEIPT'))
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument('--reconcile', metavar='RUN_ID')
    recovery.add_argument('--reconcile-legacy', metavar='RUN_ID')
    args = parser.parse_args()
    contract = load_contract()
    require_owner(contract)
    if args.native:
        return _native_worker(*args.native)
    if args.reconcile or args.reconcile_legacy:
        result = reconcile_pending(contract, args.reconcile or args.reconcile_legacy,
                                   legacy=bool(args.reconcile_legacy))
        print(json.dumps(result, sort_keys=True))
        return 0
    job_id = args.job_id or Path.cwd().name
    jobs = json.loads((Path(contract['state_dir']) / 'jobs-original.json').read_text())['jobs']
    matches = [job for job in jobs if job['id'] == job_id]
    if len(matches) != 1:
        raise OwnershipError('Original managed job missing or ambiguous')
    print(execute_job(contract, matches[0]), end='')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'Ownership operation refused: {exc}', file=sys.stderr)
        raise SystemExit(1)

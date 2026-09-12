#!/usr/bin/env python3
"""Owner cron transaction. Native scheduler remains the schedule/delivery owner.

Only execute pre-authorized scoped jobs here. Advisory locks and root routing
prevent accidents by cooperating same-user processes, not hostile shell access.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_ownership_common import OwnershipError, load_contract, owner_lock, require_owner


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise OwnershipError(f'Git operation failed: {args[0]}: {result.stderr.strip()}')
    return result.stdout.strip()


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
    elif cleanup.get("cleanup_error") or cleanup["survivor_count"]:
        success, error = False, 'Unable to stop all native job descendants'
    elif cleanup["live_count"]:
        success, error = False, 'Native job left background descendants; stopped before publication'
    Path(receipt).write_text(json.dumps(dict(success=success, document=document,
                                           response=response, error=error,
                                           descendant_cleanup=cleanup)), encoding='utf-8')
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
        if pending.exists():
            raise OwnershipError(f'Preserved failed operation blocks writers: {pending}')
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
        pending.write_text(json.dumps(dict(job=job_id, root=str(root), run=str(run_dir), base=base)))
        git(repo, 'worktree', 'add', '--detach', str(root), base)
        routed = dict(job, workdir=str(root))
        # Native job fields (models, tools, skills, prompts, gate, context) survive.
        routed['prompt'] = (job.get('prompt') or '') + (
            f'\nOwnership execution root: {root}. This is the ONLY writable vault for this run. '
            'Resolve every vault path, script and descendant against HERMES_VAULT_ROOT. '
            'Canonical/read snapshots are read-only. Do not publish or leave background workers.')
        response = executor(routed, root, run_dir)
        if git(root, 'rev-parse', 'HEAD') != base:
            raise OwnershipError('Managed agent changed HEAD; preserve for recovery')
        names = validate_diff(root, job.get('allowed_paths'))
        if names:
            git(root, 'commit', '-m', f"Managed vault job {job_id}\n\nVault-Ownership-Job: {job_id}\n"
                f"Source-Host: {contract['hostname']}\nSession: {run_id}\nBase-SHA: {base}")
            published = publish(root, contract, base)
            git(repo, 'merge', '--ff-only', published)
        pending.unlink()  # Publication/no-change success precedes housekeeping.
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
    args = parser.parse_args()
    contract = load_contract()
    require_owner(contract)
    if args.native:
        return _native_worker(*args.native)
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

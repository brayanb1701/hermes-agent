"""Pure role reconciliation. Local scheduler state is never portable authority."""
from copy import deepcopy
from pathlib import Path

VOLATILE = {'last_run_at', 'last_status', 'last_error', 'last_delivery_error',
            'last_dispatch', 'fire_claim', 'failure_streak', 'origin', 'paused_at',
            'paused_reason', 'next_run_at'}
# Preserve all native fields in the outer job except its executor and executable context.
EXECUTION_FIELDS = {'script', 'no_agent', 'workdir', 'prompt', 'skills', 'skill',
                    'enabled_toolsets', 'context_from', 'model', 'provider', 'base_url'}


def shared_maintenance(job):
    return (job.get('name') == 'darwin-vault-ownership-sync'
            and job.get('script') == 'vault_contributions.py'
            and job.get('no_agent') is True)


def one_shot(job):
    repeat = job.get('repeat') or {}
    return (job.get('schedule') or {}).get('kind') == 'once' or repeat.get('times') is not None


def index(raw):
    jobs = raw.get('jobs', [])
    result = {job['id']: deepcopy(job) for job in jobs}
    if len(result) != len(jobs):
        raise ValueError('Duplicate job IDs')
    return result


def classification(contract):
    managed, host = contract.get('managed_jobs'), contract.get('host_job_ids')
    if not isinstance(managed, dict) or not isinstance(host, list) or set(managed) & set(host):
        raise ValueError('Explicit disjoint managed_jobs and host_job_ids classification required')
    return managed, set(host)


def unwrap(job, originals):
    if job.get('script') == 'vault_ownership.py':
        if job['id'] not in originals:
            raise ValueError('Wrapper lacks original definition: ' + job['id'])
        result = deepcopy(originals[job['id']])
        for field, value in job.items():
            if field not in EXECUTION_FIELDS and field != 'ownership_managed':
                result[field] = deepcopy(value)
        return result
    return deepcopy(job)


def reconcile(contract, bundle, local, originals):
    managed, host = classification(contract)
    bundled, current, saved = index(bundle), index(local), index(originals)
    shared = {jid for jid, job in bundled.items() if shared_maintenance(job)}
    unknown = set(bundled) - set(managed) - host - shared
    if unknown:
        raise ValueError('Unclassified bundled jobs: ' + ', '.join(sorted(unknown)))
    result = deepcopy(current)
    for jid in shared:
        result.setdefault(jid, deepcopy(bundled[jid]))
    for jid in managed:
        if shared_maintenance(current.get(jid, bundled.get(jid, {}))):
            raise ValueError('Ownership maintenance must never be wrapped as a managed writer')
        if jid not in current and jid not in bundled:
            continue
        source = unwrap(current[jid], saved) if jid in current else deepcopy(bundled[jid])
        if jid not in current and one_shot(source):
            continue  # consumed and owner-local reminders must never be cloned
        # Existing local original definitions win over bundle defaults, including
        # routing, consumed reminder state, model/tool choices and maintenance.
        source.update(deepcopy(managed[jid]))
        saved[jid] = source
        job = deepcopy(source)
        if contract['role'] != 'owner':
            job.update(enabled=False, state='paused', next_run_at=None,
                       paused_reason='Contributor role: canonical writers disabled')
        else:
            job.update(script='vault_ownership.py', no_agent=True,
                       workdir=str(Path(contract['state_dir']) / 'jobs' / jid),
                       ownership_managed=True)
        result[jid] = job
    # Host maintenance is machine-local. New hosts configure their own CI; do
    # not import a foreign machine's enabled CI or update branch from a bundle.
    return {'jobs':list(result.values())}, {'jobs':list(saved.values())}


def export_jobs(contract, local, originals):
    managed, host = classification(contract)
    saved = index(originals)
    output=[]
    for job in local.get('jobs', []):
        if job['id'] not in managed and job['id'] not in host and not shared_maintenance(job):
            continue  # unclassified local tasks stay local and untouched
        item = unwrap(job, saved)
        if one_shot(item):
            continue
        for field in VOLATILE:
            item.pop(field, None)
        item.pop('ownership_managed', None)
        if isinstance(item.get('repeat'), dict):
            item['repeat']['completed'] = 0
        if item['id'] in managed:
            item.update(enabled=False, state='paused')
        output.append(item)
    return {'_portable_note':'Original job definitions only; machine-local role authorizes activation.', 'jobs':output}

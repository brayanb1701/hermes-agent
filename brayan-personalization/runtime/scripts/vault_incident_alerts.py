"""Bounded incident alert admission. This records admission, NOT delivery."""
import fcntl
import hashlib
from pathlib import Path
import re
from vault_ownership_common import OwnershipError


class RepeatedIncident(OwnershipError):
    """A still-blocked incident already admitted an alert for this exact reason."""
    def __init__(self,run,reason):
        super().__init__(reason); self.run=run; self.reason=reason


def admit_alert(contract,run,reason):
    from vault_ownership import _atomic_write_json,_read_json
    if not re.fullmatch('[0-9a-f]{32}',run):
        raise OwnershipError('Invalid incident identity')
    state=Path(contract['state_dir']); state.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(reason.encode()).hexdigest()
    directory=state/'incident-alerts'; directory.mkdir(exist_ok=True)
    with (directory/'admission.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=directory/(run+'.json')
        prior=_read_json(path,'incident alert admission') if path.exists() else None
        if prior and prior.get('reason_digest')==digest: return False
        _atomic_write_json(path,{'version':1,'run':run,'reason_digest':digest,
            'reason':reason[:512],'alert':'admitted-not-delivery-confirmed','block':'persisting'})
        paths=sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime)
        for stale in paths[:-128]: stale.unlink()
        return True


def reconcile_for_writer(contract):
    from vault_ownership import _reconcile_locked,_read_json
    try: return _reconcile_locked(contract)
    except OwnershipError as exc:
        marker=Path(contract['state_dir'])/'pending-owner.json'
        if marker.exists() and not marker.is_symlink():
            saved=_read_json(marker,'blocked incident marker')
            run=saved.get('run') or saved.get('id')
            if isinstance(run,str) and re.fullmatch('[0-9a-f]{32}',run):
                if not admit_alert(contract,run,str(exc)):
                    raise RepeatedIncident(run,str(exc)) from exc
        raise

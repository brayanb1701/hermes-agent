"""Minimal recognized atomic native-intake journal and conservative recovery."""
import re
from pathlib import Path
from vault_ownership_common import OwnershipError


def terminal_units_empty(marker):
    from vault_run_scope import scope_state, CGROUP_ROOT, _retired_empty
    units=marker.get('terminal_units')
    if (not isinstance(units,list) or len(units)>128 or len(set(units))!=len(units)
            or any(not isinstance(u,str) or not re.fullmatch(
                r'vault-intake-'+re.escape(marker['terminal_id'])+r'-[0-9a-f]{32}\.scope',u) for u in units)):
        raise OwnershipError('Invalid recorded intake terminal unit identities')
    for unit in units:
        fields=scope_state(unit)
        if fields.get('LoadState')=='not-found' or _retired_empty(fields): continue
        expected=f'/user.slice/user-{__import__("os").getuid()}.slice/user@{__import__("os").getuid()}.service/app.slice/{unit}'
        if fields.get('ControlGroup')!=expected:
            raise OwnershipError('Intake terminal cgroup identity mismatch')
        try:
            events=(CGROUP_ROOT/expected.lstrip('/')/'cgroup.events').read_text()
        except OSError as exc: raise OwnershipError('Intake terminal emptiness unverified') from exc
        if dict(line.split() for line in events.splitlines()).get('populated')!='0':
            raise OwnershipError('Intake terminal scope is populated; operator required')


def reconcile_intake(contract,marker,expected_run=None):
    from vault_ownership import git,_remote_head,_fsync_directory
    required={'kind','version','id','session_key','message_id','base','phase','terminal_id','terminal_units'}
    if (set(marker)!=required or marker.get('kind')!='native-intake' or marker.get('version')!=2
            or marker.get('phase') not in {'editing','committed','published'}
            or not re.fullmatch('[0-9a-f]{32}',str(marker.get('id')))
            or not re.fullmatch('[0-9a-f]{32}',str(marker.get('terminal_id')))
            or not re.fullmatch('[0-9a-f]{40,64}',str(marker.get('base')))
            or any(not isinstance(marker.get(k),str) or not marker[k] for k in ('session_key','message_id'))):
        raise OwnershipError('Unrecognized native-intake journal; operator required')
    if expected_run and expected_run!=marker['id']:
        raise OwnershipError('Pending intake differs from requested identity')
    terminal_units_empty(marker)
    root=Path(contract['repo_path']); state=Path(contract['state_dir'])
    if git(root,'symbolic-ref','HEAD')!=f"refs/heads/{contract['branch']}":
        raise OwnershipError('Intake canonical is on wrong branch')
    if git(root,'status','--porcelain=v1','-uall'):
        raise OwnershipError('Intake canonical is dirty; operator required')
    head=git(root,'rev-parse','HEAD')
    if marker['phase']=='editing':
        if head!=marker['base']: raise OwnershipError('Intake HEAD moved; operator required')
    else:
        parents=git(root,'rev-list','--parents','-n','1',head).split()
        message=git(root,'log','-1','--format=%B')
        trailers=message.splitlines()
        if (parents!=[head,marker['base']] or trailers.count('Session: '+marker['id'])!=1
                or trailers.count('Capture-ID: '+marker['message_id'])!=1
                or trailers.count('Base-SHA: '+marker['base'])!=1
                or _remote_head(root,contract)!=head):
            raise OwnershipError('Intake commit not positively published; operator required')
    (state/'pending-owner.json').unlink(); _fsync_directory(state)
    return {'status':'intake-cleared','run':marker['id'],'phase':marker['phase']}

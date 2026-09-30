"""Project scan outcomes come from persisted evidence, not child prose."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from test_vault_ownership import SCRIPTS, load_module, contract, write_contract


def setup_scan(tmp_path, monkeypatch, slugs=('good', 'blocked')):
    # conftest sets TZ=UTC in the environment; refresh libc too so subprocess
    # dates and in-process dates agree around local midnight.
    __import__('time').tzset()
    home = tmp_path / 'home'
    cfg = contract(home)
    write_contract(home, cfg)
    vault = Path(cfg['state_dir']) / 'worktrees' / 'project-job' / 'run'
    monkeypatch.setenv('HERMES_HOME', str(home))
    monkeypatch.setenv('HERMES_VAULT_ROOT', str(vault))
    sys.path.insert(0, str(SCRIPTS))
    scanner = load_module(SCRIPTS / 'project_review_scan.py', 'outcome_scan')
    scanner.configure(vault, tmp_path / 'workspaces')
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for slug in slugs:
        hub = vault / 'projects' / slug / 'README.md'
        hub.parent.mkdir(parents=True)
        hub.write_text(f'---\ntitle: {slug}\nstatus: paused\npriority: p1\nnext_review: {yesterday}\n---\n\n## Review notes\n')
    (vault / 'projects' / 'backlog.md').write_text('\n'.join(f'projects/{s}/README' for s in slugs))
    scanner.PROMPT_TEMPLATE_PATH.parent.mkdir(parents=True)
    scanner.PROMPT_TEMPLATE_PATH.write_text('Project slug: {{slug}}')
    executable = tmp_path / 'fake-hermes'
    executable.write_text(f'#!{sys.executable}\nimport os,pathlib,sys,datetime\nprompt=sys.argv[-1]\nif "Project slug: good" in prompt:\n p=pathlib.Path(os.environ["HERMES_VAULT_ROOT"])/"projects/good/README.md"\n today=datetime.date.today()\n old=(today-datetime.timedelta(days=1)).isoformat()\n p.write_text(p.read_text().replace(old,(today+datetime.timedelta(days=5)).isoformat())+"\\n### "+today.isoformat()+"\\nReviewed, still paused.\\n")\nprint("I successfully reviewed everything")\n')
    executable.chmod(0o755)
    monkeypatch.setattr(scanner.shutil, 'which', lambda _: str(executable))
    monkeypatch.setattr(sys, 'argv', ['project_review_scan.py', '--vault', str(vault), '--workspace-root', str(tmp_path / 'workspaces')])
    return scanner, vault


def test_scan_flags_zero_exit_child_without_saved_review(tmp_path, monkeypatch, capsys):
    scanner, vault = setup_scan(tmp_path, monkeypatch)
    scanner.main()
    output = capsys.readouterr().out
    assert output.splitlines()[0] == '[CRON_FAILURE]'
    assert 'blocked' in output and 'no-review-evidence' in output
    assert 'good' in output
    assert 'Reviewed, still paused.' in (vault / 'projects/good/README.md').read_text()


def test_failed_child_is_not_hidden_by_completed_pid_lock(tmp_path, monkeypatch, capsys):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('blocked',))
    scanner.STATE_DIR.mkdir(parents=True)
    (scanner.STATE_DIR / 'blocked.json').write_text(json.dumps({'pid': 1, 'launched_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}))
    scanner.main()
    assert capsys.readouterr().out.splitlines()[0] == '[CRON_FAILURE]'
    scanner.main()
    assert capsys.readouterr().out.splitlines()[0] == '[CRON_FAILURE]'
    assert len(list(scanner.LOG_DIR.glob('blocked.*.log'))) == 2


def test_native_script_publishes_good_review_but_reports_partial_failure(tmp_path, monkeypatch, capsys):
    import shutil
    from test_vault_ownership import init_repo, git, RUNNER
    scanner, vault = setup_scan(tmp_path, monkeypatch)
    git_dir = tmp_path / 'git'
    git_dir.mkdir()
    repo, remote = init_repo(git_dir)
    shutil.copytree(vault / 'projects', repo / 'projects')
    git(repo, 'add', 'projects')
    git(repo, 'commit', '-m', 'project fixtures')
    git(repo, 'push', 'origin', 'main')
    cfg = contract(scanner.HERMES_HOME, repo=repo)
    cfg['remote'] = str(remote)
    write_contract(scanner.HERMES_HOME, cfg)
    scripts = scanner.HERMES_HOME / 'scripts'
    scripts.mkdir()
    for name in ('project_review_scan.py', 'project_review_history_retention.py', 'vault_ownership_common.py'):
        shutil.copyfile(SCRIPTS / name, scripts / name)
    shutil.copyfile(tmp_path / 'fake-hermes', tmp_path / 'hermes')
    with (tmp_path / 'hermes').open('a') as stream:
        stream.write('print(\'{"ready_count": 0}\')\n')
    (tmp_path / 'hermes').chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + ':' + __import__('os').environ['PATH'])
    runner = load_module(RUNNER, 'project_native_outcome_runner')
    with pytest.raises(runner.AgentDeclaredFailure):
        runner.execute_job(cfg, {'id':'project-test', 'script':'project_review_scan.py', 'no_agent':True,
            'allowed_paths':['projects/'], 'ownership_timeout':30})
    assert capsys.readouterr().out.splitlines()[0] == '[CRON_FAILURE]'
    assert 'Reviewed, still paused.' in (repo / 'projects/good/README.md').read_text()
    assert not (Path(cfg['state_dir']) / 'pending-owner.json').exists()
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0]


@pytest.mark.parametrize('existing_today', [False, True])
def test_pruning_and_old_same_day_entry_do_not_prove_child_success(tmp_path, monkeypatch, capsys, existing_today):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('blocked',))
    hub = vault / 'projects/blocked/README.md'
    dates = [date.today() - timedelta(days=offset) for offset in range(1, 8)]
    if existing_today:
        dates.append(date.today())
    hub.write_text(hub.read_text() + '\n'.join(f'### {day.isoformat()}\nOld review\n' for day in dates))
    scanner.main()
    assert capsys.readouterr().out.splitlines()[0] == '[CRON_FAILURE]'
    assert hub.read_text().count('### ') == 5


def test_all_saved_reviews_have_no_failure_marker(tmp_path, monkeypatch, capsys):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('good',))
    scanner.main()
    output = capsys.readouterr().out
    assert '[CRON_FAILURE]' not in output, output + '\nHUB=' + (vault/'projects/good/README.md').read_text() + '\nPROMPT=' + '\n'.join(p.read_text() for p in scanner.STATE_DIR.glob('*.txt'))
    assert 'good (review): ok;' in output
    assert not list(scanner.STATE_DIR.glob('*.json'))


def test_workspace_only_review_update_is_not_success(tmp_path, monkeypatch):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('blocked',))
    hub = vault / 'projects/blocked/README.md'
    today = date.today().isoformat()
    hub.write_text(hub.read_text().replace('status: paused', 'status: active').replace('priority: p1', f'priority: p1\nlast_meaningful_update: {today}\nreview_cadence: 5d'))
    (vault / 'projects/dashboard.md').write_text('projects/blocked/README')
    (vault / 'projects/backlog.md').write_text('')
    workspace = scanner.WORKSPACE_ROOT / 'blocked'
    workspace.mkdir(parents=True)
    (workspace / 'PROJECT_STATUS.md').write_text('---\nstatus: active\n---\n')
    changelog = workspace / 'PROJECT_CHANGELOG.md'
    changelog.write_text(f'---\nnext_review: {today}\n---\n')
    child = tmp_path / 'fake-hermes'
    child.write_text(f'#!{sys.executable}\nfrom pathlib import Path\np=Path({str(changelog)!r})\np.write_text(p.read_text().replace({today!r}, {(date.today()+timedelta(days=5)).isoformat()!r}))\n')
    item = scanner.collect_inventory(vault)[0][0]
    result = scanner.launch_project(item)
    assert result['outcome'] == 'no-review-evidence'
    assert 'will not auto-retry' in result['retry_warning']


def test_workspace_due_date_is_consumed_by_saved_review_not_future_hub_date(tmp_path, monkeypatch):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('blocked',))
    hub = vault / 'projects/blocked/README.md'
    reviewed = date.today() - timedelta(days=1)
    hub.write_text(hub.read_text().replace('status: paused', 'status: active')
        .replace('priority: p1', 'priority: p1\nlast_meaningful_update: 2000-01-01\nreview_cadence: 5d')
        .replace(reviewed.isoformat(), (date.today()+timedelta(days=5)).isoformat())
        + f'### {reviewed.isoformat()}\nReviewed, no execution progress.\n')
    (vault / 'projects/dashboard.md').write_text('projects/blocked/README')
    (vault / 'projects/backlog.md').write_text('')
    workspace = scanner.WORKSPACE_ROOT / 'blocked'
    workspace.mkdir(parents=True)
    (workspace / 'PROJECT_STATUS.md').write_text('---\nstatus: active\n---\n')
    changelog = workspace / 'PROJECT_CHANGELOG.md'
    changelog.write_text(f'---\nnext_review: {reviewed.isoformat()}\n---\n')
    assert scanner.collect_inventory(vault)[0] == []
    changelog.write_text(f'---\nnext_review: {date.today().isoformat()}\n---\n')
    ready = scanner.collect_inventory(vault)[0]
    assert ready[0]['trigger_reason'] == 'workspace next_review is due'
    # Without dated review evidence, legacy due-workspace behavior remains.
    hub.write_text(hub.read_text().split('### ')[0])
    assert scanner.collect_inventory(vault)[0][0]['mode'] == 'review'


def test_heading_review_does_not_acknowledge_dates_inside_bullets(tmp_path, monkeypatch):
    scanner, vault = setup_scan(tmp_path, monkeypatch, slugs=('blocked',))
    old = date.today() - timedelta(days=2)
    text = f'## Review notes\n### {old.isoformat()}\n- {date.today().isoformat()}: sent draft, not a review\n'
    assert scanner.latest_review_date(text) == old
    assert scanner.review_entries_today(text) == set()


def test_live_scan_requires_owned_worktree_root(tmp_path, monkeypatch):
    scanner, vault = setup_scan(tmp_path, monkeypatch)
    monkeypatch.delenv('HERMES_VAULT_ROOT')
    with pytest.raises(SystemExit, match='ownership worktree'):
        scanner.main()

"""V2 run containment contracts: never inspect unrelated user processes."""
from pathlib import Path
import sys
import pytest
from test_vault_ownership import RUNNER, load_module

load_module(RUNNER, 'scope_runner_imports')


def test_intent_identity_and_prior_boot_proof(tmp_path):
    module = load_module(RUNNER.parent / 'vault_run_scope.py', 'scope_tests')
    intent = module.scope_intent('a'*32, tmp_path)
    assert intent['unit'] == 'vault-run-' + 'a'*32 + '.scope'
    assert intent['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    bad = dict(intent, unit='unrelated.scope')
    with pytest.raises(module.OwnershipError): module.validate_intent(bad, 'a'*32, tmp_path)
    prior = dict(intent, boot_id='00000000-0000-0000-0000-000000000000')
    proof = module.close_scope(prior, 'a'*32, tmp_path)
    assert proof['contained'] and proof['status'] == 'prior-boot'


def test_booked_identity_cannot_be_replaced(tmp_path, monkeypatch):
    module = load_module(RUNNER.parent / 'vault_run_scope.py', 'scope_identity_tests')
    intent = module.scope_intent('b'*32, tmp_path)
    intent['booking'] = {'invocation_id':'a'*32, 'cgroup':intent['expected_cgroup'], 'pid':123, 'start_time':1}
    monkeypatch.setattr(module,'scope_state',lambda unit: {'LoadState':'loaded', 'ControlGroup':intent['expected_cgroup'], 'InvocationID':'b'*32})
    with pytest.raises(module.OwnershipError, match='identity'):
        module.close_scope(intent,'b'*32,tmp_path)

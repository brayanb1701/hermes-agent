"""Per incident/reason bounded alert admission, not fictitious delivery."""
from test_vault_ownership import RUNNER,load_module,contract


def test_same_incident_same_reason_dedupes_new_reason_alerts(tmp_path):
    load_module(RUNNER,'alert_imports')
    module=load_module(RUNNER.parent/'vault_incident_alerts.py','alert_tests')
    cfg=contract(tmp_path/'home')
    assert module.admit_alert(cfg,'a'*32,'canonical dirty') is True
    assert module.admit_alert(cfg,'a'*32,'canonical dirty') is False
    assert module.admit_alert(cfg,'a'*32,'scope not empty') is True
    assert module.admit_alert(cfg,'a'*32,'scope not empty') is False
    assert module.admit_alert(cfg,'b'*32,'canonical dirty') is True

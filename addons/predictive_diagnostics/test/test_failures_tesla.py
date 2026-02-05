from addons.predictive_diagnostics.knowledge.registry import (
    get_failure_by_id,
    get_failure_modes_for_system,
)


def test_tesla_failures_registered():
    tesla_ids = [f.id for f in get_failure_modes_for_system("tesla_hv_battery")]
    assert "tesla_hv_isolation_fault" in tesla_ids
    assert "tesla_contactor_failure" in tesla_ids


def test_tesla_lookup_by_id():
    fm = get_failure_by_id("tesla_ptc_heater_failure")
    assert fm is not None
    assert fm.name.startswith("Tesla PTC Cabin/Battery Heater")


def test_tesla_alert_placeholders():
    iso = get_failure_by_id("tesla_hv_isolation_fault")
    assert iso is not None
    # We encode initial expected_alerts based on known alert names in comments
    assert "BMS_f035" in iso.expected_alerts

    ptc = get_failure_by_id("tesla_ptc_heater_failure")
    assert ptc is not None
    assert "BMS_f035" in ptc.expected_alerts

    charge = get_failure_by_id("tesla_charge_port_fault")
    assert charge is not None
    assert "charge_port_fault" in charge.expected_alerts

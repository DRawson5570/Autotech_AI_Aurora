from addons.predictive_diagnostics.knowledge.registry import (
    get_failure_by_id,
    get_failure_modes_for_system,
    get_failures_for_dtc,
)


def test_ev_failures_registered():
    ev_ids = [f.id for f in get_failure_modes_for_system("ev_battery")]
    assert "hv_battery_cell_imbalance" in ev_ids
    assert "battery_thermal_runaway_risk" in ev_ids


def test_phev_failures_registered():
    phev_ids = [f.id for f in get_failure_modes_for_system("phev_hybrid")]
    assert "phev_mode_transition_fault" in phev_ids
    assert "phev_regen_brake_blending_fault" in phev_ids


def test_failure_lookup_by_dtc():
    # DTC in EV file
    matches = get_failures_for_dtc("P0A00")
    assert any(f.id == "hv_battery_cell_imbalance" for f in matches)

    # DTC in PHEV file
    matches2 = get_failures_for_dtc("P0A0D")
    assert any(f.id == "phev_mode_transition_fault" for f in matches2)

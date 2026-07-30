import pytest

from modules.forzahorizon.redline import RedlineDetector, predict_redline_rpm


WHEELS = ("fl", "fr", "rl", "rr")


def _telemetry(**overrides):
    value = {
        "on": True,
        "max_rpm": 8000.0,
        "idle_rpm": 900.0,
        "rpm": 7000.0,
        "gear": 3,
        "accel": 230,
        "clutch": 0,
        "speed": 100.0,
        "power": 120_000.0,
        "torque": 300.0,
        "car_ordinal": 101,
        "car_performance_index": 800,
        "num_cylinders": 8,
    }
    for wheel in WHEELS:
        value[f"tire_slip_ratio_{wheel}"] = 0.0
        value[f"tire_combined_slip_{wheel}"] = 0.0
    value.update(overrides)
    return value


def _confirmed_cut(
    detector,
    start,
    rpm,
    *,
    cut_power=0.0,
    cut_torque=0.0,
    cut_rpm_drop=40.0,
    confirm_rpm_drop=50.0,
    **overrides,
):
    detector.update(
        _telemetry(
            rpm=rpm,
            power=120_000.0,
            torque=300.0,
            **overrides,
        ),
        start,
    )
    pending = detector.update(
        _telemetry(
            rpm=rpm - cut_rpm_drop,
            power=cut_power,
            torque=cut_torque,
            **overrides,
        ),
        start + 0.02,
    )
    assert pending.limiter_active is False
    return detector.update(
        _telemetry(
            rpm=rpm - confirm_rpm_drop,
            power=100_000.0,
            torque=260.0,
            **overrides,
        ),
        start + 0.15,
    )


def test_prediction_uses_the_reference_curve_and_clamps():
    assert predict_redline_rpm(5000.0) == pytest.approx(4250.0)
    assert predict_redline_rpm(10500.0) == pytest.approx(10206.0)
    assert predict_redline_rpm(2000.0) == pytest.approx(1600.0)
    assert predict_redline_rpm(20000.0) == pytest.approx(19600.0)
    assert predict_redline_rpm(0.0) == 0.0


def test_prediction_does_not_mutate_raw_dashboard_maximum():
    detector = RedlineDetector()
    telemetry = _telemetry()

    state = detector.update(telemetry, 0.0)

    assert telemetry["max_rpm"] == 8000.0
    assert "effective_redline_rpm" not in telemetry
    assert state.effective_rpm == pytest.approx(predict_redline_rpm(8000.0))
    assert state.learned is False


def test_electric_disables_alert_but_still_detects_limit_internally():
    detector = RedlineDetector()
    electric = {"gear": 1, "num_cylinders": 0}
    first = detector.update(_telemetry(rpm=7600.0, **electric), 0.0)
    armed = detector.update(_telemetry(rpm=7600.0, **electric), 0.40)

    assert first.redline_alert_allowed is False
    assert armed.redline_alert_allowed is False
    assert armed.limiter_active is False

    detector.update(
        _telemetry(rpm=7560.0, power=0.0, torque=0.0, **electric),
        0.42,
    )
    confirmed = detector.update(
        _telemetry(rpm=7550.0, power=100_000.0, torque=260.0, **electric),
        0.56,
    )

    assert confirmed.redline_alert_allowed is False
    assert confirmed.limiter_active is True


def test_electric_second_forward_gear_does_not_reenable_redline_alert():
    detector = RedlineDetector()

    first = detector.update(
        _telemetry(gear=1, num_cylinders=0),
        0.0,
    )
    second = detector.update(
        _telemetry(gear=2, num_cylinders=0),
        0.10,
    )

    assert first.redline_alert_allowed is False
    assert second.redline_alert_allowed is False


def test_electric_alert_stays_disabled_across_forward_and_neutral_gears():
    detector = RedlineDetector()

    first = detector.update(
        _telemetry(gear=1, num_cylinders=0),
        0.0,
    )
    second = detector.update(
        _telemetry(gear=2, num_cylinders=0),
        0.10,
    )
    neutral = detector.update(
        _telemetry(gear=11, num_cylinders=0),
        0.20,
    )
    back_in_first = detector.update(
        _telemetry(gear=1, num_cylinders=0),
        0.30,
    )

    assert first.redline_alert_allowed is False
    assert second.redline_alert_allowed is False
    assert neutral.redline_alert_allowed is False
    assert back_in_first.redline_alert_allowed is False


def test_combustion_first_gear_and_missing_cylinder_data_keep_ratio_warning():
    detector = RedlineDetector()

    combustion = detector.update(
        _telemetry(gear=1, num_cylinders=4),
        0.0,
    )
    telemetry = _telemetry(gear=1)
    telemetry.pop("num_cylinders")
    legacy_mapping = detector.update(telemetry, 0.10)

    assert combustion.redline_alert_allowed is True
    assert legacy_mapping.redline_alert_allowed is True


def test_powertrain_change_switches_alert_gate_from_telemetry_identity():
    detector = RedlineDetector()
    electric = detector.update(
        _telemetry(gear=2, num_cylinders=0),
        0.0,
    )
    changed_to_combustion = detector.update(
        _telemetry(gear=1, num_cylinders=4),
        0.10,
    )
    changed_back_to_electric = detector.update(
        _telemetry(gear=4, num_cylinders=0),
        0.20,
    )

    assert electric.redline_alert_allowed is False
    assert changed_to_combustion.redline_alert_allowed is True
    assert changed_back_to_electric.redline_alert_allowed is False


def test_midrange_power_drop_is_not_treated_as_limiter():
    detector = RedlineDetector()
    detector.update(_telemetry(rpm=4500.0), 0.0)
    detector.update(_telemetry(rpm=4500.0), 0.40)

    state = detector.update(
        _telemetry(rpm=4450.0, power=0.0, torque=0.0),
        0.42,
    )
    state = detector.update(_telemetry(rpm=4400.0), 0.60)

    assert state.limiter_active is False
    assert state.learned is False


def test_large_dashboard_red_zone_bootstraps_from_repeated_fuel_cuts():
    detector = RedlineDetector()
    large_red_zone = {"max_rpm": 12_000.0, "idle_rpm": 900.0}
    detector.update(_telemetry(rpm=6100.0, **large_red_zone), 0.0)
    detector.update(_telemetry(rpm=6100.0, **large_red_zone), 0.40)

    cut_shape = {
        "cut_power": 8_000.0,
        "cut_torque": 20.0,
        "cut_rpm_drop": 90.0,
        "confirm_rpm_drop": 100.0,
    }
    first = _confirmed_cut(
        detector,
        0.50,
        6200.0,
        **cut_shape,
        **large_red_zone,
    )
    second = _confirmed_cut(
        detector,
        0.90,
        6240.0,
        **cut_shape,
        **large_red_zone,
    )
    third = _confirmed_cut(
        detector,
        1.30,
        6180.0,
        **cut_shape,
        **large_red_zone,
    )

    predicted = predict_redline_rpm(large_red_zone["max_rpm"])
    assert 6200.0 < predicted * 0.82
    assert first.limiter_active is False
    assert first.learned is False
    assert second.limiter_active is True
    assert second.learned is False
    assert third.limiter_active is True
    assert third.learned is True
    assert third.confidence == pytest.approx(0.6)
    assert third.effective_rpm == pytest.approx(6200.0, abs=60.0)


def test_unclustered_broad_power_cuts_do_not_become_a_limiter():
    detector = RedlineDetector()
    large_red_zone = {"max_rpm": 12_000.0, "idle_rpm": 900.0}
    detector.update(_telemetry(rpm=4000.0, **large_red_zone), 0.0)
    detector.update(_telemetry(rpm=4000.0, **large_red_zone), 0.40)

    first = _confirmed_cut(detector, 0.50, 4200.0, **large_red_zone)
    second = _confirmed_cut(detector, 0.90, 5200.0, **large_red_zone)
    third = _confirmed_cut(detector, 1.30, 6200.0, **large_red_zone)

    assert first.limiter_active is False
    assert second.limiter_active is False
    assert third.limiter_active is False
    assert third.learned is False


def test_electric_power_cuts_below_prediction_do_not_broad_bootstrap():
    detector = RedlineDetector()
    electric = {
        "max_rpm": 12_000.0,
        "idle_rpm": 0.0,
        "gear": 1,
        "num_cylinders": 0,
    }
    detector.update(_telemetry(rpm=6100.0, **electric), 0.0)
    detector.update(_telemetry(rpm=6100.0, **electric), 0.40)

    first = _confirmed_cut(detector, 0.50, 6200.0, **electric)
    second = _confirmed_cut(detector, 0.90, 6240.0, **electric)
    third = _confirmed_cut(detector, 1.30, 6180.0, **electric)

    assert first.limiter_active is False
    assert second.limiter_active is False
    assert third.limiter_active is False
    assert third.learned is False
    assert third.redline_alert_allowed is False


def test_shift_during_confirmation_discards_power_cut():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7150.0), 0.40)
    detector.update(_telemetry(rpm=7120.0, power=0.0, torque=0.0), 0.42)

    shifted = detector.update(
        _telemetry(gear=4, rpm=6100.0, power=80_000.0),
        0.48,
    )
    settled = detector.update(_telemetry(gear=4, rpm=6200.0), 0.70)

    assert shifted.limiter_active is False
    assert settled.limiter_active is False
    assert settled.learned is False


def test_relative_power_and_torque_collapse_detects_nonzero_fuel_cut():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7150.0), 0.40)
    detector.update(
        _telemetry(rpm=7060.0, power=8_000.0, torque=30.0),
        0.42,
    )

    confirmed = detector.update(
        _telemetry(rpm=7050.0, power=100_000.0, torque=260.0),
        0.56,
    )

    assert confirmed.limiter_active is True
    assert confirmed.confidence > 0.0


def test_three_same_gear_fuel_cuts_learn_median_redline():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7100.0), 0.40)

    first = _confirmed_cut(detector, 0.50, 7200.0)
    second = _confirmed_cut(detector, 0.90, 7240.0)
    third = _confirmed_cut(detector, 1.30, 7180.0)

    assert first.limiter_active is True
    assert second.learned is False
    assert third.learned is True
    assert third.confidence == pytest.approx(0.6)
    assert third.effective_rpm == pytest.approx(7200.0, abs=60.0)


def test_severe_wheelspin_cannot_train_the_detector():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7150.0), 0.40)
    slipping = {"tire_slip_ratio_rr": 3.0}

    detector.update(
        _telemetry(rpm=7120.0, power=0.0, torque=0.0, **slipping),
        0.42,
    )
    state = detector.update(_telemetry(rpm=7100.0, **slipping), 0.60)

    assert state.limiter_active is False
    assert state.learned is False


def test_car_or_tuning_change_resets_learned_limit():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7100.0), 0.40)
    _confirmed_cut(detector, 0.50, 7200.0)
    _confirmed_cut(detector, 0.90, 7210.0)
    learned = _confirmed_cut(detector, 1.30, 7190.0)
    assert learned.learned is True

    changed = detector.update(
        _telemetry(car_performance_index=850, rpm=6000.0),
        2.0,
    )

    assert changed.learned is False
    assert changed.confidence == 0.0
    assert changed.effective_rpm == pytest.approx(predict_redline_rpm(8000.0))


def test_menu_packet_with_zero_identity_preserves_learning():
    detector = RedlineDetector()
    detector.update(_telemetry(), 0.0)
    detector.update(_telemetry(rpm=7100.0), 0.40)
    _confirmed_cut(detector, 0.50, 7200.0)
    _confirmed_cut(detector, 0.90, 7210.0)
    learned = _confirmed_cut(detector, 1.30, 7190.0)
    assert learned.learned is True

    menu = detector.update(
        _telemetry(on=False, car_ordinal=0, car_performance_index=0),
        2.0,
    )
    resumed = detector.update(_telemetry(rpm=7000.0), 2.5)

    assert menu.learned is True
    assert resumed.learned is True
    assert resumed.effective_rpm == pytest.approx(learned.effective_rpm)

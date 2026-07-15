from modules.config.settings import Settings
from modules.forzahorizon.collision import CollisionDetector


def _telemetry(**overrides):
    value = {
        "on": True,
        "accel_x": 0.0,
        "accel_z": 0.0,
        "smashable_vel_diff": 0.0,
    }
    value.update(overrides)
    return value


def test_collision_detector_reports_direction_source_and_normalized_intensity():
    detector = CollisionDetector()
    settings = Settings()
    detector.update(_telemetry(), settings, 1.0)

    signal = detector.update(
        _telemetry(accel_x=10.0, smashable_vel_diff=15.0),
        settings,
        1.01,
    )

    assert signal is not None
    assert signal.direction == "left"
    assert signal.source == "both"
    assert signal.intensity == 1.0


def test_collision_detector_requires_a_clear_sample_after_cooldown_to_rearm():
    detector = CollisionDetector()
    settings = Settings()
    detector.update(_telemetry(), settings, 1.0)
    assert detector.update(
        _telemetry(smashable_vel_diff=15.0), settings, 1.01
    ) is not None

    assert detector.update(
        _telemetry(smashable_vel_diff=15.0), settings, 1.50
    ) is None
    assert detector.update(_telemetry(), settings, 1.51) is None
    assert detector.update(
        _telemetry(smashable_vel_diff=15.0), settings, 1.52
    ) is not None


def test_collision_detector_resets_when_telemetry_leaves_race():
    detector = CollisionDetector()
    settings = Settings()
    detector.update(_telemetry(accel_x=20.0), settings, 1.0)

    assert detector.update({"on": False}, settings, 1.1) is None
    assert detector.update(_telemetry(accel_x=20.0), settings, 1.2) is None

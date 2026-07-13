import struct

import pytest

from modules.forzahorizon.udp_listener import parse_packet


def test_puddle_depth_fields_are_parsed_as_float32():
    packet = bytearray(324)
    expected = {
        "wheel_in_puddle_fl": 0.25,
        "wheel_in_puddle_fr": 0.5,
        "wheel_in_puddle_rl": 0.75,
        "wheel_in_puddle_rr": 1.0,
    }
    for offset, value in zip((132, 136, 140, 144), expected.values()):
        struct.pack_into("<f", packet, offset, value)

    telemetry = parse_packet(packet)

    for name, value in expected.items():
        assert telemetry[name] == pytest.approx(value)

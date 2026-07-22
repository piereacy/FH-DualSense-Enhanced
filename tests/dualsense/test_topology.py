from modules.dualsense.topology import StableTopology, path_key


def _info(path, *, bus=1):
    return {"path": path, "bus_type": bus, "product_id": 0x0CE6}


def test_topology_requires_two_consecutive_observations():
    tracker = StableTopology(required_observations=2)
    usb = _info(b"usb-path")

    assert tracker.observe([usb]) == ()
    assert tracker.observe([]) == ()
    assert tracker.observe([usb]) == ()
    assert tracker.observe([usb]) == (usb,)


def test_topology_tracks_presence_before_candidate_is_stable():
    tracker = StableTopology(required_observations=2)

    tracker.observe([_info("Path-One")])

    assert tracker.is_present("path-one") is True
    assert tracker.is_present("other") is False


def test_path_key_is_case_insensitive_for_bytes_and_text():
    assert path_key({"path": b"bthenum\\abc"}) == path_key(
        {"path": "BTHENUM\\ABC"}
    )

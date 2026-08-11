from __future__ import annotations

from plugins.gfriends import backend as gfriends


def test_payload_name_candidates_preserves_spaced_actor_names():
    names = gfriends._payload_name_candidates(["倉本 すみれ", "Nozomi Kuramoto,仓本堇"])

    assert "倉本 すみれ" in names
    assert "Nozomi Kuramoto" in names
    assert "仓本堇" in names
    assert "すみれ" not in names
    assert "Kuramoto" not in names

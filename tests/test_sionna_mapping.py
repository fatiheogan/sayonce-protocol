"""Tests for the Sionna 5G NR experiment's pure helpers (sionna_nr/mapping.py).

They need neither Sionna nor PyTorch, so they run in CI like the rest of the suite.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sionna_nr"))

from mapping import ASSUMPTIONS, link_profile, load_bler, tbler_at  # noqa: E402


def test_tbler_interpolation_is_monotone_and_bounded():
    curve = (np.array([0.0, 1.0, 2.0, 3.0]), np.array([0.9, 0.3, 0.05, 0.004]))
    snr = np.linspace(-5, 6, 50)
    b = tbler_at(curve, snr)
    assert np.all(np.diff(b) <= 1e-12)
    assert b[0] == pytest.approx(1.0)  # left of the curve: every block fails
    assert tbler_at(curve, np.array([1.0]))[0] == pytest.approx(0.3)
    assert 0.05 < tbler_at(curve, np.array([1.5]))[0] < 0.3  # log-linear between points
    assert np.all((b >= 0) & (b <= 1))


def test_load_bler_sorts_by_snr(tmp_path: Path):
    p = tmp_path / "bler.csv"
    p.write_text("mcs,snr_db,tbler\n9,2,0.5\n9,0,1.0\n9,1,0.8\n3,-1,0.2\n")
    curves = load_bler(p)
    assert sorted(curves) == [3, 9]
    assert list(curves[9][0]) == [0.0, 1.0, 2.0]
    assert list(curves[9][1]) == [1.0, 0.8, 0.5]


def test_link_profile_maps_harq_to_delay_and_residual_loss():
    good = link_profile("x", 50e6, 0.0)
    assert good["bandwidth_mbps"] == pytest.approx(50.0)
    assert good["loss"] == 0.0
    base = ASSUMPTIONS["core_one_way_delay_ms"] + 2.5 / 2
    assert good["delay_ms"] == pytest.approx(base)

    edge = link_profile("y", 0.5e6, 0.1)
    # residual loss after 4 HARQ transmissions, extra delay from expected retransmissions
    assert edge["loss"] == pytest.approx(0.1 ** ASSUMPTIONS["harq_max_tx"], rel=1e-2)
    extra = (0.1 + 0.01 + 0.001) * ASSUMPTIONS["harq_rtt_ms"]
    assert edge["delay_ms"] == pytest.approx(base + extra, abs=0.01)


def test_profile_never_means_unlimited_bandwidth():
    # bandwidth 0 means "unlimited" in the emulator; a served UE must always map to a positive rate
    assert link_profile("z", 10.0, 0.05)["bandwidth_mbps"] > 0
    with pytest.raises(ValueError):
        link_profile("outage", 0.0, 1.0)

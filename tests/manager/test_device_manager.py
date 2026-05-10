# Copyright (c) 2026 pslBot contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for DeviceManager and RingBuffer."""

from __future__ import annotations

import numpy as np
import pytest

from pslbot.manager.device_manager import DeviceManager, RingBuffer


# ---------------------------------------------------------------------------
# RingBuffer
# ---------------------------------------------------------------------------


class TestRingBuffer:
    """Tests for the lock-free ring buffer."""

    def test_push_read(self) -> None:
        buf = RingBuffer(capacity=8, dtype=np.float32, channels=1)
        assert buf.available == 0
        buf.push(np.zeros(4, dtype=np.float32))
        assert buf.available == 4
        out = buf.read(4)
        assert out.shape == (4,)
        assert buf.available == 0

    def test_overwrite(self) -> None:
        buf = RingBuffer(capacity=4, dtype=np.float32, channels=1)
        buf.push(np.array([1, 2], dtype=np.float32))
        buf.push(np.array([3, 4], dtype=np.float32))
        assert buf.available == 4
        buf.push(np.array([5, 6], dtype=np.float32))
        assert buf.available == 4
        out = buf.read(4)
        np.testing.assert_array_equal(out, np.array([3, 4, 5, 6], dtype=np.float32))

    def test_read_empty(self) -> None:
        buf = RingBuffer(capacity=4, dtype=np.float32, channels=1)
        out = buf.read(100)
        assert out.shape == (0,)

    def test_stereo(self) -> None:
        buf = RingBuffer(capacity=4, dtype=np.float32, channels=2)
        frames = np.array([[1, 10], [2, 20]], dtype=np.float32)
        buf.push(frames)
        out = buf.read(2)
        assert out.shape == (2, 2)
        np.testing.assert_array_equal(out, frames)

    def test_read_partial(self) -> None:
        buf = RingBuffer(capacity=16, dtype=np.float32, channels=1)
        buf.push(np.arange(10, dtype=np.float32))
        out = buf.read(5)
        assert out.shape == (5,)
        assert buf.available == 5


# ---------------------------------------------------------------------------
# DeviceManager
# ---------------------------------------------------------------------------


class TestDeviceManager:
    """Tests for device enumeration and DeviceManager lifecycle."""

    def test_enumerate_returns_list(self) -> None:
        devices = DeviceManager.enumerate_devices()
        assert isinstance(devices, list)
        for d in devices:
            assert "name" in d
            assert "index" in d
            assert "channels_in" in d

    def test_get_default_device_returns_optional_tuple(self) -> None:
        result = DeviceManager.get_default_device()
        if result is not None:
            idx, name, channels = result
            assert isinstance(idx, int)
            assert isinstance(name, str)
            assert channels >= 1

    def test_init_no_start(self) -> None:
        dm = DeviceManager()
        assert dm.status["state"] == "idle"
        assert dm.status["device_name"] is None
        assert dm.buffer.available == 0

    def test_status_dict_keys(self) -> None:
        dm = DeviceManager()
        st = dm.status
        assert "state" in st
        assert "device_name" in st
        assert "channels" in st
        assert "latency_ms" in st
        assert "buffer_fill_pct" in st
        assert "total_frames" in st
        assert "drop_count" in st
        assert "silence_count" in st
        assert "timeout_remaining" in st
        assert "silence_remaining" in st

    def test_stop_when_idle(self) -> None:
        dm = DeviceManager()
        dm.stop()  # Should not raise
        assert dm.status["state"] == "idle"


@pytest.mark.skipif(
    not DeviceManager.get_default_device(),
    reason="No audio input device available",
)
class TestDeviceManagerLive:
    """Live tests that require an audio input device."""

    def test_start_stop(self) -> None:
        dm = DeviceManager(timeout_s=1.0, silence_s=5.0)
        dm.start()
        import time
        time.sleep(0.5)
        st = dm.status
        assert st["state"] in ("running", "error")
        if st["state"] == "running":
            assert st["device_name"] is not None
            assert st["channels"] >= 1
            assert st["total_frames"] > 0
        dm.stop()

    def test_raw_buffer(self) -> None:
        dm = DeviceManager(timeout_s=1.0, silence_s=5.0)
        dm.start()
        import time
        time.sleep(0.3)
        raw = dm.raw_buffer(0.1)
        assert isinstance(raw, np.ndarray)
        assert raw.ndim == 1
        dm.stop()

# Copyright (c) 2026 pslBot contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for SessionMonitor."""

from __future__ import annotations

import numpy as np
import pytest

from pslbot.manager.session_monitor import MonitorConfig, SessionMonitor


class TestMonitorConfig:
    """Tests for MonitorConfig."""

    def test_defaults(self) -> None:
        cfg = MonitorConfig()
        assert cfg.silence_threshold == 0.01
        assert cfg.silence_s == 30.0
        assert cfg.timeout_s == 300.0
        assert cfg.min_signal_rms == 0.001
        assert cfg.noise_profile == "auto"

    def test_custom(self) -> None:
        cfg = MonitorConfig(silence_threshold=0.05, noise_profile="off")
        assert cfg.silence_threshold == 0.05
        assert cfg.noise_profile == "off"


class TestSessionMonitor:
    """Tests for SessionMonitor state machine."""

    def test_initial_state(self) -> None:
        mon = SessionMonitor()
        assert mon.state == "idle"
        assert mon.signal_detected is False
        assert mon.silence_detected is False

    def test_start_sets_running(self) -> None:
        mon = SessionMonitor()
        mon.start()
        assert mon.state == "running"

    def test_stop_sets_stopped(self) -> None:
        mon = SessionMonitor()
        mon.start()
        mon.stop()
        assert mon.state == "stopped"

    def test_process_zeros_sets_silence(self) -> None:
        cfg = MonitorConfig(silence_s=0.1, timeout_s=10.0)
        mon = SessionMonitor(cfg)
        mon.start()
        zeros = np.zeros(4410, dtype=np.float32)  # 0.1s at 44100 Hz
        mon.process(zeros, 44100)
        assert mon.silence_detected is True

    def test_process_signal_sets_signal_detected(self) -> None:
        cfg = MonitorConfig(min_signal_rms=0.001, silence_s=30.0, timeout_s=300.0)
        mon = SessionMonitor(cfg)
        mon.start()
        # Generate a sine wave with enough amplitude
        t = np.linspace(0, 0.1, 4410, dtype=np.float32)
        signal = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        mon.process(signal, 44100)
        assert mon.signal_detected is True

    def test_report_keys(self) -> None:
        cfg = MonitorConfig()
        mon = SessionMonitor(cfg)
        mon.start()
        report = mon.report()
        assert "state" in report
        assert "level_db" in report
        assert "signal_detected" in report
        assert "silence_detected" in report
        assert "silence_remaining" in report
        assert "timeout_remaining" in report

    def test_process_while_stopped_warns(self) -> None:
        mon = SessionMonitor()
        # Should not raise, just warn
        mon.process(np.zeros(1024, dtype=np.float32), 44100)

import pytest

import src.dms.config as dms_config


def test_config_defaults():
    config = dms_config.load_dms_config()

    for key, value in dms_config.DEFAULT_DMS_CONFIG.items():
        assert key in config
        assert config[key] == value


def test_config_validation_chunk_size(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
dms:
  chunk_size: 0
  chunk_overlap: 1
  max_file_size_mb: 50
"""
    )

    with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
        dms_config.load_dms_config(config_file)


def test_config_validation_overlap(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
dms:
  chunk_size: 10
  chunk_overlap: 10
  max_file_size_mb: 50
"""
    )

    with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
        dms_config.load_dms_config(config_file)


def test_config_missing_section(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        """
search:
  engine: searxng
"""
    )

    config = dms_config.load_dms_config(config_file)

    assert config == dms_config.DEFAULT_DMS_CONFIG

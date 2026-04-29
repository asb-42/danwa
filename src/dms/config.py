
import yaml

DEFAULT_DMS_CONFIG = {
    "enabled": True,
    "storage_path": "dms_storage",
    "chunk_size": 512,
    "chunk_overlap": 51,
    "embedding_model": "intfloat/multilingual-e5-small",
    "ocr_enabled": False,
    "ocr_device": "cpu",
    "max_file_size_mb": 50,
    "chroma_collection": "document_chunks",
    "memory_dir": "memory",
}


def load_dms_config(config_path="config/settings.yaml"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    dms_config = {**DEFAULT_DMS_CONFIG, **(config.get("dms") or {})}

    chunk_size = dms_config["chunk_size"]
    chunk_overlap = dms_config["chunk_overlap"]
    max_file_size_mb = dms_config["max_file_size_mb"]

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")
    if max_file_size_mb <= 0:
        raise ValueError("max_file_size_mb must be greater than 0")

    return dms_config

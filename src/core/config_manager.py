import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings_path = self.config_dir / "settings.yaml"
        self.llm_profiles_path = self.config_dir / "llm_profiles.yaml"
        self.prompt_variants_path = self.config_dir / "prompt_variants.yaml"

    def _load_yaml(self, path: Path) -> Any:
        if not path.exists():
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, path: Path, data: Any):
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"Config saved to {path}")

    # --- Settings ---
    def get_settings(self) -> Dict:
        return self._load_yaml(self.settings_path)

    def update_settings(self, new_settings: Dict):
        # Basic validation could be added here
        self._save_yaml(self.settings_path, new_settings)

    # --- LLM Profiles ---
    def get_llm_profiles(self) -> Dict:
        return self._load_yaml(self.llm_profiles_path)

    def get_llm_profile(self, profile_name: str) -> Optional[Dict]:
        profiles = self.get_llm_profiles()
        return profiles.get("profiles", {}).get(profile_name)

    def add_llm_profile(self, profile_name: str, profile_data: Dict):
        config = self.get_llm_profiles()
        if "profiles" not in config:
            config["profiles"] = {}
        config["profiles"][profile_name] = profile_data
        self._save_yaml(self.llm_profiles_path, config)

    def update_llm_profile(self, profile_name: str, profile_data: Dict):
        self.add_llm_profile(profile_name, profile_data)

    def delete_llm_profile(self, profile_name: str):
        config = self.get_llm_profiles()
        if "profiles" in config and profile_name in config["profiles"]:
            del config["profiles"][profile_name]
            self._save_yaml(self.llm_profiles_path, config)
            return True
        return False

    # --- Prompt Variants ---
    def get_prompt_variants(self) -> Dict:
        return self._load_yaml(self.prompt_variants_path)

    def get_prompt_variant(self, variant_name: str) -> Optional[Dict]:
        config = self.get_prompt_variants()
        return config.get("variants", {}).get(variant_name)

    def add_prompt_variant(self, variant_name: str, variant_data: Dict):
        config = self.get_prompt_variants()
        if "variants" not in config:
            config["variants"] = {}
        config["variants"][variant_name] = variant_data
        self._save_yaml(self.prompt_variants_path, config)

    def update_prompt_variant(self, variant_name: str, variant_data: Dict):
        self.add_prompt_variant(variant_name, variant_data)

    def delete_prompt_variant(self, variant_name: str):
        config = self.get_prompt_variants()
        if "variants" in config and variant_name in config["variants"]:
            del config["variants"][variant_name]
            self._save_yaml(self.prompt_variants_path, config)
            return True
        return False

    def set_default_variant(self, variant_name: str):
        config = self.get_prompt_variants()
        config["default_variant"] = variant_name
        self._save_yaml(self.prompt_variants_path, config)

    # --- Generic Config Access ---
    def get_config(self, config_name: str) -> Dict:
        """Loads any YAML file in the config directory."""
        path = self.config_dir / f"{config_name}.yaml"
        return self._load_yaml(path)

    def save_config(self, config_name: str, data: Dict):
        """Saves data to any YAML file in the config directory."""
        path = self.config_dir / f"{config_name}.yaml"
        self._save_yaml(path, data)
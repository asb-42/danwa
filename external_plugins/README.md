# External Plugins
#
# This directory contains external plugins that can be loaded by the
# Input Composer or Output Composer plugin registries.
#
# Each plugin must have:
#   - manifest.json — PluginManifest descriptor
#   - plugin.py — Plugin class (InputPlugin or OutputPlugin subclass)
#
# SECURITY: Only load plugins from trusted sources. External plugins
# are disabled by default. Set DANWA_ALLOW_EXTERNAL_PLUGINS=true to enable.

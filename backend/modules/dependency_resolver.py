"""Dependency Resolver — validates module dependency constraints using semver.

Uses the ``packaging`` library for proper semver comparison
(``>=1.0.0``, ``^2.0.0``, ``~3.0.1``, etc.).

Supports two kinds of dependencies:
- **module deps**: ``{module_id: semver_constraint}`` — validated against installed versions
- **role deps**: ``[role_name, ...]`` — validated against installed agent-core modules
"""

from __future__ import annotations

import logging
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when a dependency constraint is not satisfied."""


class DependencyCycleError(DependencyError):
    """Raised when a circular dependency is detected."""


class DependencyResolver:
    """Resolves and validates module dependency constraints."""

    def resolve(
        self,
        module_id: str,
        dependencies: dict[str, str],
        installed: dict[str, str],
    ) -> list[str]:
        """Validate that all module-level dependencies are satisfied.

        Args:
            module_id: The module requesting validation (for error messages).
            dependencies: ``{module_id: constraint_string}`` from the manifest.
            installed: ``{module_id: version_string}`` of all installed modules.

        Returns:
            List of error messages (empty if all satisfied).

        Example:
            >>> resolver = DependencyResolver()
            >>> errors = resolver.resolve(
            ...     "my-module",
            ...     {"dep-a": ">=1.0.0", "dep-b": "^2.0.0"},
            ...     {"dep-a": "2.0.0", "dep-b": "2.5.0"},
            ... )
            >>> assert errors == []
        """
        errors: list[str] = []
        for dep_id, constraint in dependencies.items():
            if dep_id not in installed:
                errors.append(f"Missing dependency '{dep_id}' required by '{module_id}' (constraint: {constraint})")
                continue

            installed_version = installed[dep_id]
            try:
                spec = Requirement(f"{dep_id}{constraint}").specifier
                ver = Version(installed_version)
                if not spec.contains(ver):
                    errors.append(
                        f"Dependency '{dep_id}' version {installed_version} does not satisfy constraint {constraint} required by '{module_id}'"
                    )
            except (InvalidRequirement, InvalidVersion) as exc:
                errors.append(f"Invalid dependency constraint for '{dep_id}': constraint={constraint}, error={exc}")

        return errors

    @staticmethod
    def resolve_roles(
        module_id: str,
        required_roles: list[str],
        installed_modules: list[dict[str, Any]],
    ) -> tuple[list[str], dict[str, str]]:
        """Check which required roles are satisfied by installed agent-core modules.

        Args:
            module_id: The module requesting validation (for error messages).
            required_roles: List of role names the module depends on.
            installed_modules: List of all installed module info dicts (must have
                ``module_id``, ``type``, ``role``).

        Returns:
            Tuple of ``(errors, role_map)`` where ``errors`` is a list of warning
            messages for unsatisfied roles, and ``role_map`` maps each required
            role to the chosen module_id.

        The resolver picks the first enabled module with a matching ``role``
        field, preferring modules whose tags include ``"default"``.
        """
        errors: list[str] = []
        role_map: dict[str, str] = {}

        # Build lookup: role → [module_info, ...]
        role_index: dict[str, list[dict[str, Any]]] = {}
        for mod in installed_modules:
            mod_role = mod.get("role", "")
            if mod_role:
                role_index.setdefault(mod_role, []).append(mod)

        for role in required_roles:
            candidates = role_index.get(role, [])
            if not candidates:
                errors.append(f"Module '{module_id}' requires role '{role}' but no installed module provides it")
                continue

            # Prefer module tagged "default"
            best = candidates[0]
            for c in candidates:
                if "default" in c.get("tags", []):
                    best = c
                    break
            role_map[role] = best.get("module_id", "")

        return errors, role_map

    @staticmethod
    def find_missing_roles(
        required_roles: list[str],
        installed_modules: list[dict[str, Any]],
    ) -> list[str]:
        """Return the subset of ``required_roles`` not satisfied by any installed module.

        Args:
            required_roles: Role names to check.
            installed_modules: List of installed module info dicts.

        Returns:
            List of role names that have no installed provider.
        """
        available_roles = {mod.get("role", "") for mod in installed_modules if mod.get("role")}
        return [r for r in required_roles if r not in available_roles]

    @staticmethod
    def detect_cycles(
        module_id: str,
        dependencies: dict[str, str],
        all_deps: dict[str, dict[str, str]],
        visited: set[str] | None = None,
        stack: set[str] | None = None,
    ) -> list[str]:
        """Detect circular dependencies using DFS.

        Args:
            module_id: Starting module ID.
            dependencies: Direct dependencies of the starting module.
            all_deps: ``{module_id: {dependency_id: constraint}}`` for all modules.
            visited: Set of visited nodes (internal recursion).
            stack: Current recursion stack (internal recursion).

        Returns:
            List of error messages (empty if no cycles).

        Example:
            >>> resolver = DependencyResolver()
            >>> errors = resolver.detect_cycles(
            ...     "a", {"b": ">=1.0"}, {"b": {"c": ">=1.0"}, "c": {"a": ">=1.0"}}
            ... )
            >>> assert len(errors) > 0  # a -> b -> c -> a
        """
        if visited is None:
            visited = set()
        if stack is None:
            stack = set()

        errors: list[str] = []
        stack.add(module_id)

        for dep_id in dependencies:
            if dep_id not in all_deps:
                continue
            if dep_id in stack:
                # Extract the cycle for a clear message
                cycle_parts = []
                for part in list(stack):
                    cycle_parts.append(part)
                    if part == dep_id:
                        break
                cycle_parts.append(dep_id)
                errors.append(f"Circular dependency detected: {' → '.join(cycle_parts)}")
                continue
            if dep_id not in visited:
                visited.add(dep_id)
                sub_errors = DependencyResolver.detect_cycles(
                    dep_id,
                    all_deps.get(dep_id, {}),
                    all_deps,
                    visited,
                    stack,
                )
                errors.extend(sub_errors)

        stack.remove(module_id)
        return errors

    @staticmethod
    def collect_all_dependencies(
        installed_modules: list[dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        """Build a full dependency map from a list of installed module dicts.

        Args:
            installed_modules: List of module dicts (must have 'module_id' and 'dependencies').

        Returns:
            ``{module_id: {dep_id: constraint}}`` map.
        """
        result: dict[str, dict[str, str]] = {}
        for mod in installed_modules:
            mid = mod.get("module_id", "")
            deps = mod.get("dependencies", {})
            if isinstance(deps, dict):
                # Handle both legacy flat dict and new structured format
                if "modules" in deps:
                    modules_part = deps.get("modules", {})
                    if isinstance(modules_part, dict):
                        result[mid] = modules_part
                else:
                    result[mid] = deps
        return result

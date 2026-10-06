"""Dependency-rule checks (Clean Architecture) enforced as tests."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def _violations(package: str, forbidden: tuple[str, ...]) -> list[str]:
    found = []
    for path in (APP / package).rglob("*.py"):
        for module in _imports(path):
            if module.startswith(forbidden):
                found.append(f"{path.relative_to(APP)} -> {module}")
    return found


def test_domain_has_no_framework_or_outer_layer_imports():
    forbidden = ("fastapi", "sqlalchemy", "redis", "app.application",
                 "app.infrastructure", "app.presentation", "app.core")
    assert _violations("domain", forbidden) == []


def test_application_does_not_use_global_settings_or_infrastructure():
    forbidden = ("fastapi", "sqlalchemy", "app.core", "app.infrastructure",
                 "app.presentation")
    assert _violations("application", forbidden) == []


def test_routes_never_import_concrete_infrastructure():
    assert _violations("presentation/routes", ("app.infrastructure", "sqlalchemy")) == []


def test_fare_calculator_lives_in_domain():
    from app.domain.billing import FareCalculator

    assert FareCalculator.__module__ == "app.domain.billing"

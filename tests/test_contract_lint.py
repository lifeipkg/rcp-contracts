"""contract_lint 的反向测试：每条检查都必须能抓到对应的违反。

正向只证明"当前契约没坏"，反向才证明"坏了会红"。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

_LINT_PATH = Path(__file__).resolve().parent.parent / "tools" / "contract_lint.py"
_spec = importlib.util.spec_from_file_location("contract_lint", _LINT_PATH)
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)

def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _contracts(tmp_path: Path, *, openapi: dict | None = None) -> Path:
    contracts = tmp_path / "repo"
    spec = openapi or {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1.0.0"},
        "paths": {
            "/x": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["a"],
                                    "properties": {
                                        "a": {"type": "string"},
                                        "b": {"type": "integer"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    _write(contracts / "contracts" / "openapi" / "svc.yaml", spec)
    return contracts


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


def test_clean_contracts_have_no_findings(tmp_path: Path):
    contracts = _contracts(tmp_path)
    assert lint.check_refs(contracts) == []


def test_missing_ref_target_is_error(tmp_path: Path):
    contracts = _contracts(tmp_path)
    _write(
        contracts / "contracts" / "schemas" / "extra.yaml",
        {"type": "object", "properties": {"status": {"$ref": "ghost.yaml"}}},
    )
    assert "E401" in _codes(lint.check_refs(contracts))


def test_existing_relative_ref_is_clean(tmp_path: Path):
    contracts = _contracts(tmp_path)
    _write(contracts / "contracts" / "schemas" / "base.yaml", {"type": "string"})
    _write(
        contracts / "contracts" / "schemas" / "extra.yaml",
        {"type": "object", "properties": {"status": {"$ref": "base.yaml"}}},
    )
    assert lint.check_refs(contracts) == []


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def test_removed_field_and_new_required_field_are_breaking(tmp_path: Path):
    contracts = _contracts(tmp_path)
    _git(contracts, "init", "-q")
    _git(contracts, "add", "-A")
    _git(contracts, "commit", "-qm", "base")
    _git(contracts, "tag", "base")

    changed = {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1.0.0"},
        "paths": {
            "/x": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["a", "c"],
                                    "properties": {
                                        "a": {"type": "string"},
                                        "c": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    _write(contracts / "contracts" / "openapi" / "svc.yaml", changed)

    messages = [f.message for f in lint.check_breaking(contracts, "base")]
    assert any("入参字段被删除 b" in m for m in messages), messages
    assert any("新增必填字段 c" in m for m in messages), messages


def test_removed_operation_is_breaking(tmp_path: Path):
    contracts = _contracts(tmp_path)
    _git(contracts, "init", "-q")
    _git(contracts, "add", "-A")
    _git(contracts, "commit", "-qm", "base")
    _git(contracts, "tag", "base")

    _write(
        contracts / "contracts" / "openapi" / "svc.yaml",
        {"openapi": "3.0.3", "info": {"title": "t", "version": "1.0.0"}, "paths": {}},
    )
    messages = [f.message for f in lint.check_breaking(contracts, "base")]
    assert any("接口被删除 POST /x" in m for m in messages), messages


def test_cli_exit_codes(tmp_path: Path):
    contracts = _contracts(tmp_path)
    assert lint.main(["--contracts", str(contracts)]) == 0
    assert lint.main(["--contracts", str(tmp_path / "ghost")]) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

#!/usr/bin/env python3
"""契约层静态检查：$ref 可解析、决策枚举不内联、与基线的破坏性变更。

这是"契约能不能对表"的静态下限，不是运行时契约测试（Pact / provider verification
需要起服务，本工作区无真实集群，不在此假装做到）。三项检查都可离线复算：

    python tools/contract_lint.py --contracts .                    # 引用 + 决策内联
    python tools/contract_lint.py --contracts . --baseline HEAD~1   # 追加破坏性变更对比

退出码：0 无错误；1 有错误；2 输入不可用。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

DECISION_ENUM_FILE = Path("contracts/schemas/decision.yaml")

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT = 2


class Finding:
    __slots__ = ("level", "code", "message")

    def __init__(self, level: str, code: str, message: str) -> None:
        self.level = level
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "code": self.code, "message": self.message}


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def iter_nodes(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """深度遍历，产出 (路径, 节点)。"""
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_nodes(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_nodes(value, f"{path}[{index}]")


def iter_refs(node: Any) -> Iterator[str]:
    for _, value in iter_nodes(node):
        if isinstance(value, dict) and isinstance(value.get("$ref"), str):
            yield value["$ref"]


def ref_target(ref: str, base_dir: Path) -> Path | None:
    """把 $ref 解析成文件路径；纯片段引用（#/...）返回 None。"""
    if ref.startswith("#"):
        return None
    file_part = ref.split("#", 1)[0]
    if not file_part:
        return None
    return (base_dir / file_part).resolve()


def decision_enum(contracts: Path) -> list[str]:
    data = load_yaml(contracts / DECISION_ENUM_FILE) or {}
    return list(data.get("enum") or [])


def yaml_files(contracts: Path) -> list[Path]:
    return sorted(
        path
        for path in (contracts / "contracts").rglob("*.yaml")
        if path.is_file()
    )


def check_refs(contracts: Path) -> list[Finding]:
    """E401 跨文件 $ref 必须解析到真实文件。"""
    findings: list[Finding] = []
    for path in yaml_files(contracts):
        rel = path.relative_to(contracts).as_posix()
        try:
            spec = load_yaml(path)
        except yaml.YAMLError as exc:
            findings.append(Finding("error", "E401", f"{rel} YAML 解析失败: {exc}"))
            continue
        for ref in iter_refs(spec):
            target = ref_target(ref, path.parent)
            if target is None:
                continue
            if not target.is_file():
                findings.append(
                    Finding("error", "E401", f"{rel} 的 $ref 指向不存在的文件: {ref}")
                )
    return findings


def check_decision_not_inlined(contracts: Path) -> list[Finding]:
    """RL-003：决策枚举只能 $ref，不得内联。

    两种违反形态都抓：字段名为 decision 却写死 enum；任意字段内联了与 Decision
    完全相同的取值集合（换个名字内联同样会失去唯一真源）。
    """
    findings: list[Finding] = []
    canonical = set(decision_enum(contracts))

    for path in yaml_files(contracts):
        if path == contracts / DECISION_ENUM_FILE:
            continue
        rel = path.relative_to(contracts).as_posix()
        try:
            spec = load_yaml(path)
        except yaml.YAMLError:
            continue
        for node_path, node in iter_nodes(spec):
            if not isinstance(node, dict):
                continue
            enum = node.get("enum")
            if not isinstance(enum, list) or not enum:
                continue
            attribute = node_path.rsplit(".", 1)[-1].split("[", 1)[0]
            if attribute == "decision":
                findings.append(
                    Finding(
                        "error",
                        "RL-003",
                        f"{rel}#{node_path} 内联了 decision 枚举；应改为 $ref decision.yaml",
                    )
                )
            elif canonical and set(enum) == canonical:
                findings.append(
                    Finding(
                        "error",
                        "RL-003",
                        f"{rel}#{node_path} 内联了与 Decision 完全相同的取值集合；"
                        f"应改为 $ref decision.yaml",
                    )
                )
    return findings


def _schema_shape(schema: Any) -> dict[str, Any]:
    """抽取用于对比的结构：(属性名 → 类型, required 集合)。"""
    if not isinstance(schema, dict):
        return {"properties": {}, "required": set()}
    properties = schema.get("properties") or {}
    shape = {}
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            shape[name] = "unknown"
            continue
        if "$ref" in prop:
            shape[name] = f"$ref:{prop['$ref']}"
        elif prop.get("type") == "array":
            items = prop.get("items") or {}
            shape[name] = f"array<{items.get('type', '?')}>"
        else:
            shape[name] = str(prop.get("type", "?"))
    return {"properties": shape, "required": set(schema.get("required") or [])}


def collect_operations(spec: Any) -> dict[str, dict[str, Any]]:
    """{ "POST /path": {属性名: 类型}, "POST /path#required": {...} } 的扁平化视图。"""
    operations: dict[str, dict[str, Any]] = {}
    if not isinstance(spec, dict):
        return operations
    for raw_path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            if not isinstance(operation, dict):
                continue
            key = f"{method.upper()} {raw_path}"
            entry: dict[str, Any] = {"properties": {}, "required": set(), "parameters": set()}
            body = operation.get("requestBody") or {}
            for media in (body.get("content") or {}).values():
                if isinstance(media, dict):
                    shape = _schema_shape(media.get("schema"))
                    entry["properties"].update(shape["properties"])
                    entry["required"] |= shape["required"]
            for parameter in operation.get("parameters") or []:
                if isinstance(parameter, dict) and parameter.get("name"):
                    entry["parameters"].add(str(parameter["name"]))
                    if parameter.get("required"):
                        entry["required"].add(str(parameter["name"]))
            operations[key] = entry
    return operations


def _baseline_spec(contracts: Path, baseline: str, rel: str) -> Any | None:
    """从 git 基线里读同一份契约；读不到返回 None（视为新增文件，无破坏性变更）。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(contracts), "show", f"{baseline}:{rel}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return yaml.safe_load(result.stdout)
    except yaml.YAMLError:
        return None


def check_breaking(contracts: Path, baseline: str) -> list[Finding]:
    """E402：删除接口、删除字段、新增必填字段、改字段类型，均视为破坏性变更。"""
    findings: list[Finding] = []
    for path in yaml_files(contracts):
        rel = path.relative_to(contracts).as_posix()
        if not path.is_file():
            continue
        old_spec = _baseline_spec(contracts, baseline, rel)
        if old_spec is None:
            continue
        old_ops = collect_operations(old_spec)
        new_ops = collect_operations(load_yaml(path))

        for key in sorted(set(old_ops) - set(new_ops)):
            findings.append(Finding("error", "E402", f"{rel}: 接口被删除 {key}（不兼容）"))
        for key in sorted(set(old_ops) & set(new_ops)):
            old, new = old_ops[key], new_ops[key]
            for name in sorted(set(old["properties"]) - set(new["properties"])):
                findings.append(
                    Finding("error", "E402", f"{rel}: {key} 入参字段被删除 {name}（不兼容）")
                )
            for name in sorted(new["required"] - old["required"]):
                findings.append(
                    Finding("error", "E402", f"{rel}: {key} 新增必填字段 {name}（不兼容）")
                )
            for name in sorted(set(old["properties"]) & set(new["properties"])):
                if old["properties"][name] != new["properties"][name]:
                    findings.append(
                        Finding(
                            "error",
                            "E402",
                            f"{rel}: {key} 字段 {name} 类型变更 "
                            f"{old['properties'][name]} → {new['properties'][name]}（不兼容）",
                        )
                    )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="契约层静态检查")
    parser.add_argument("--contracts", required=True, type=Path, help="契约仓根目录")
    parser.add_argument("--baseline", help="git 基线（如 HEAD~1 / origin/main），给出才做破坏性对比")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    contracts = args.contracts.resolve()
    if not (contracts / "contracts").is_dir():
        print(f"[contract_lint] 输入不可用: {contracts}/contracts 不存在", file=sys.stderr)
        return EXIT_INPUT

    findings: list[Finding] = []
    findings += check_refs(contracts)
    findings += check_decision_not_inlined(contracts)
    if args.baseline:
        findings += check_breaking(contracts, args.baseline)

    errors = [f for f in findings if f.level == "error"]

    if args.json:
        print(json.dumps({
            "contracts": str(contracts),
            "baseline": args.baseline,
            "errors": [f.as_dict() for f in errors],
            "closed": not errors,
        }, ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(f"[{finding.level.upper():5}] {finding.code}: {finding.message}")
        print(f"\n结论：{len(errors)} 个错误 —— {'闭合' if not errors else '未闭合'}")

    return EXIT_OK if not errors else EXIT_FINDINGS


if __name__ == "__main__":
    sys.exit(main())

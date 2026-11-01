#!/usr/bin/env python3
"""契约→实现 机械对表。

从 OpenAPI 契约抽取路径集合，从 Java 源码抽取 Spring 路由集合，做两向差集。
只做机械事实：不判断语义、不签发放行，缺口由人补。

用法：
    python tools/contract_check.py --repo ../rcp-content-patrol \
        --contract contracts/openapi/content-patrol.yaml [--json]

退出码：0 无差集；1 存在差集；2 输入缺失或解析失败。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

MAPPING_METHODS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}


def normalize(path: str) -> str:
    path = re.sub(r"\{[^}]*\}", "{}", path.strip())
    path = re.sub(r"/+", "/", path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path or "/"


def contract_routes(contract_file: Path) -> set[str]:
    """抽取契约里的路由集合，形如 'POST /api/v1/patrol/check'。"""
    spec = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
    if not spec or "paths" not in spec:
        raise ValueError(f"{contract_file} 缺少 paths 段")
    routes = set()
    for raw_path, operations in (spec["paths"] or {}).items():
        if not isinstance(operations, dict):
            continue
        for method in operations:
            if method.lower() in {"get", "post", "put", "delete", "patch"}:
                routes.add(f"{method.upper()} {normalize(raw_path)}")
    return routes


CLASS_MAPPING = re.compile(
    r"@RequestMapping\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\""
)
METHOD_MAPPING = re.compile(
    r"@(Get|Post|Put|Delete|Patch)Mapping\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\")?"
)
REQUEST_MAPPING_METHOD = re.compile(
    r"@RequestMapping\s*\([^)]*method\s*=\s*RequestMethod\.(\w+)[^)]*?"
    r"(?:value\s*=\s*|path\s*=\s*)?\"([^\"]*)\"",
    re.S,
)


def impl_routes(repo_root: Path) -> set[str]:
    """抽取 Java 源码中 @RestController 的路由集合。"""
    java_root = repo_root / "src" / "main" / "java"
    if not java_root.is_dir():
        raise ValueError(f"{repo_root} 下没有 src/main/java")
    routes: set[str] = set()
    for java_file in sorted(java_root.rglob("*.java")):
        text = java_file.read_text(encoding="utf-8", errors="replace")
        if "@RestController" not in text:
            continue
        base_match = CLASS_MAPPING.search(text)
        base = base_match.group(1) if base_match else ""
        for kind, sub in METHOD_MAPPING.findall(text):
            method = MAPPING_METHODS[f"{kind}Mapping"]
            routes.add(f"{method} {normalize(base + (sub or ''))}")
        for method, sub in REQUEST_MAPPING_METHOD.findall(text):
            routes.add(f"{method.upper()} {normalize(base + sub)}")
    return routes


def main() -> int:
    parser = argparse.ArgumentParser(description="契约→实现 机械对表")
    parser.add_argument("--repo", required=True, type=Path, help="实现仓根目录")
    parser.add_argument("--contract", required=True, type=Path, help="OpenAPI 契约文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        want = contract_routes(args.contract)
        got = impl_routes(args.repo)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"[contract_check] 输入不可用: {exc}", file=sys.stderr)
        return 2

    missing_in_impl = sorted(want - got)
    missing_in_contract = sorted(got - want)
    diff = bool(missing_in_impl or missing_in_contract)

    if args.json:
        print(json.dumps({
            "repo": str(args.repo),
            "contract": str(args.contract),
            "contract_routes": sorted(want),
            "impl_routes": sorted(got),
            "missing_in_impl": missing_in_impl,
            "missing_in_contract": missing_in_contract,
            "closed": not diff,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"契约路由 {len(want)} 条，实现路由 {len(got)} 条")
        print(f"  契约有、实现缺: {missing_in_impl or '无'}")
        print(f"  实现有、契约缺: {missing_in_contract or '无'}")
        print("  结论:", "闭合" if not diff else "未闭合（差集非空）")

    return 0 if not diff else 1


if __name__ == "__main__":
    sys.exit(main())

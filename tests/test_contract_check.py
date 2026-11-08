"""contract_check 的反向测试：抽取规则错了必须能被抓到。

两类判据是"机械事实"的前提，前提错了结论就是假绿灯：
  1. Gin 的通配写法必须归一成契约写法，否则网关的 IAM 透传永远对不上；
  2. .agents 下的 worktree 必须跳过，否则别的分支上的实现会被当成当前实现的证据。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_CHECK_PATH = Path(__file__).resolve().parent.parent / "tools" / "contract_check.py"
_spec = importlib.util.spec_from_file_location("contract_check", _CHECK_PATH)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def _go_repo(root: Path, body: str, name: str = "main.go") -> Path:
    (root / "go.mod").write_text("module example.com/x\n\ngo 1.22\n", encoding="utf-8")
    (root / name).write_text(body, encoding="utf-8")
    return root


def test_gin_wildcards_are_normalized_to_contract_form(tmp_path: Path) -> None:
    repo = _go_repo(
        tmp_path,
        """
        r.GET("/api/v1/iam/*path", h)
        r.POST("/api/v1/iam/*path", h)
        r.PUT("/api/v1/users/:userId/password", h)
        r.POST("/api/v1/iam/login", h)
        """,
    )

    assert check.go_routes(repo) == {
        "GET /api/v1/iam/**",
        "POST /api/v1/iam/**",
        "PUT /api/v1/users/{}/password",
        "POST /api/v1/iam/login",
    }


def test_worktree_sources_are_not_counted(tmp_path: Path) -> None:
    repo = _go_repo(tmp_path, 'r.POST("/api/v1/iam/login", h)\n')
    worktree = repo / ".agents" / "worktrees" / "gw"
    worktree.mkdir(parents=True)
    (worktree / "main.go").write_text('r.GET("/api/v1/ghost/*path", h)\n', encoding="utf-8")

    routes = check.go_routes(repo)

    assert "POST /api/v1/iam/login" in routes
    assert not any("ghost" in route for route in routes), "worktree 里的路由不该算进当前实现"


def test_test_files_are_not_counted(tmp_path: Path) -> None:
    repo = _go_repo(tmp_path, 'r.POST("/api/v1/iam/login", h)\n')
    (repo / "router_test.go").write_text('r.DELETE("/api/v1/ghost", h)\n', encoding="utf-8")

    assert "DELETE /api/v1/ghost" not in check.go_routes(repo)

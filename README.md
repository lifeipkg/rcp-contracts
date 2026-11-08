# rcp-contracts · 契约仓

平台**接口契约**仓：只有 OpenAPI 与跨服务共享结构，再加对表工具与共享 CI 模板。

声明层真源不在这里——服务登记、种类、能力、红线、术语、版本钉全部在
[`rcp-ontology/ontology/`](../rcp-ontology/ontology/)。本仓只回答一个问题：
**服务之间长什么样**。

## 目录

> 平台全景（业务、架构、数据面分层、演进路线）见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)，服务清单见 [`docs/SERVICES.md`](docs/SERVICES.md)。

| 路径 | 是什么 |
|---|---|
| `contracts/openapi/*.yaml` | 各服务对外 HTTP 契约（OpenAPI 3.0.3）：`api-gateway` / `dataway` / `db-ops` / `iam` |
| `contracts/schemas/*.yaml` | 跨服务共享结构，禁止各服务内联复制 |
| `tools/contract_check.py` | 契约→实现 机械对表（OpenAPI 路由 ↔ 实现路由，两向差集；`go.mod` 存在时走 Gin 注册解析） |
| `tools/contract_lint.py` | 契约层静态检查：`$ref` 可解析、与基线无破坏性变更 |
| `tests/test_contract_lint.py` | 上一条的反向测试：每条检查都必须能抓到对应违反 |
| `docs/DISCOVERY.md` | 服务发现现状、为什么停在声明层、接线步骤与验收命令 |
| `.github/workflows/go-service.yml` | 共享 CI 模板，Go 服务仓复用（`go vet/test/build`） |

## 常用命令

```bash
# 契约→实现对表（在实现仓根目录跑，差集非空即未闭合）
python ../rcp-contracts/tools/contract_check.py \
  --repo . --contract ../rcp-contracts/contracts/openapi/iam.yaml

# 契约层静态检查（引用解析 / 与基线的破坏性变更）
python tools/contract_lint.py --contracts . --baseline origin/main

# 契约仓测试
python -m pytest -q tests

# 全量一致性（登记 / 契约 / 红线 / 仓布局 / 依赖图；--workspace 不可省）
python ../rcp-ontology/checker/cli.py check --contracts . -w ..
```

## 变更纪律

1. **声明先于契约。** 服务名、端口、能力先在 `rcp-ontology/ontology/`
   改（`tbox/` → `abox/`），再改本仓的 OpenAPI，最后改实现仓并抬钉同步。顺序反了
   `ontology check` 会红（E107 / E105 / RL-006）。
2. **改契约 → 先改本仓 → 消费仓升钉 → CI 对表闭合。** 差集非空时报告缺口清单，
   不允许改契约迎合实现（那等于把 bug 写进真源）。
3. **新增服务** → 先在 `rcp-ontology/ontology/abox/services.ttl` 登记
   （`a rcp:<Kind>, rcp:Service` + `rcp:repo` / `rcp:port` / `rcp:owner` / 能力），
   再在本仓挂 OpenAPI 契约（`rcp:contract` 指向文件路径），最后写实现（否则 RL-006 红）。
4. **新增仓** → 先在 `abox/services.ttl` 登记（`a rcp:Meta` 用于不部署的元仓），
   否则 E107 红——"目录存在但未登记"在任何环境下都判错，这是多人协作时最容易漏的一步。
5. **DDL 不进本仓，也不进业务仓，只进 `rcp-ops/migrations`**（RL-004）。
6. **无法立即消除的偏离** → 在 `rcp-ontology/ontology/policy/redlines.ttl` 登记例外
   （`scope` + `match` + `reason` + `owner` + `reviewBy`），检查器降级为提示、过期自动转红。
   **只写进文档不提例外，等于没登记。**
7. **新增红线** → 先在本体仓写 `spec`（或实现新执行器），再改调用方。
   只声明没有 `spec` 会被 E301 判为"纸面红线"。
8. **能力的 `owner` 是责任锚点**：改 owner 必须确认该服务确实持有这个能力（E112），
   并重新生成 CODEOWNERS。

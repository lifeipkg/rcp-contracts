# rcp-contracts · 契约仓

平台声明层真源。**契约先行**：任何跨服务的契约、字段、服务名、端口变更，先在本仓立，消费仓再升钉同步。

## 目录

> 平台全景（业务、架构、数据面分层、演进路线）见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)，服务清单见 [`docs/SERVICES.md`](docs/SERVICES.md)。

| 路径 | 是什么 |
|---|---|
| `registry/services.ttl` | 服务登记（RDF 图真源）：实例 IRI 即服务名，`rdf:type` 即种类，具体关系边（`calls` / `queries` …）直接是可推理的三元组。图无实例顺序，条目按名称排列。`a rcp:Meta` 的是元仓（本仓、本体仓、ops），无端口不挂契约，登记它们是为了让 owner 与仓边界有唯一出处 |
| `registry/platform.yaml` | 与图无关的平台配置：`baseline_stack` 版本真源与服务发现（`discovery` 段）。刻意不写成三元组——版本号没有图语义，写成字面量反而失去 grep 的可用性 |
| `contracts/openapi/*.yaml` | 各服务对外 HTTP 契约（OpenAPI 3.0.3） |
| `contracts/schemas/*.yaml` | 跨服务共享结构（决策、结论、事件），禁止各服务内联复制 |
| `vocabulary/terms.yaml` | 平台立名词汇表，新概念先立名。`covers` 字段挂到 TBox 种类，W303 按它判断"种类有没有立名" |
| `ontology/constraints/redlines.yaml` | 可机械检查的架构红线（RL-001 ~ RL-007）与例外登记 |
| `tools/contract_check.py` | 契约→实现 机械对表（OpenAPI 路由 ↔ Spring 路由，两向差集） |
| `tools/contract_lint.py` | 契约层静态检查：`$ref` 可解析、决策枚举未内联、与基线无破坏性变更 |
| `tests/test_contract_lint.py` | 上一条的反向测试：每条检查都必须能抓到对应违反 |
| `docs/DISCOVERY.md` | 服务发现现状、为什么停在声明层、接线步骤与验收命令 |
| `.github/workflows/java-service.yml` | 共享 CI 模板，Java 服务仓 `workflow_call` 复用 |

## 常用命令

```bash
# 版本真源
grep -A6 '^baseline_stack:' registry/platform.yaml

# 契约→实现对表（在实现仓根目录跑，差集非空即未闭合）
python ../rcp-contracts/tools/contract_check.py \
  --repo . --contract ../rcp-contracts/contracts/openapi/content-patrol.yaml

# 契约层静态检查（引用 / 决策内联 / 与基线的破坏性变更）
python tools/contract_lint.py --contracts . --baseline origin/main

# 契约仓测试
python -m pytest -q tests

# 登记/契约/红线一致性（需本体仓；--workspace 用于仓布局级红线与未登记仓检测）
python ../rcp-ontology/rcp_ontology/cli.py check --contracts . --workspace ..

# 改一个服务之前，先看它波及谁（多人协作时的必查步）
python ../rcp-ontology/rcp_ontology/cli.py impact --contracts . --service api-gateway

# 按 owner 重新生成 CODEOWNERS（改 owner 后必须重跑）
python ../rcp-ontology/rcp_ontology/cli.py owners --contracts . --org your-org --out ../CODEOWNERS
```

## 变更纪律

1. 改契约 → 先改本仓 → 消费仓升钉 → CI 对表闭合；
2. 新增服务 → 先在 `services.ttl` 登记（`a rcp:<Kind>, rcp:Service` + `rcp:repo` / `rcp:port` / `rcp:owner` / 能力 / 契约），再挂契约，最后写实现（否则 RL-006 红）；
3. 新增仓 → 先在 `services.ttl` 登记（`a rcp:Meta` 用于不部署的元仓），否则 E107 红——
   "目录存在但未登记"在任何环境下都判错，这是多人协作时最容易漏的一步；
4. 新增种类（kind）→ 先在 `rcp-ontology/concepts/tbox.ttl` 声明，且**四个布尔属性必须写全**
   （`must_be_external` / `is_entry` / `requires_port` / `requires_contract`），
   再在 `terms.yaml` 挂一个带 `covers` 的术语（否则 E113 / W303 红）；
5. 改决策等级 → 只改 `contracts/schemas/decision.yaml` 与 `rcp-core` 的 `Decision`，枚举与分值两侧必须逐字一致（RL-003）；
6. DDL 不进本仓，也不进业务仓，只进 `rcp-ops/migrations`（RL-004）；
7. 无法立即消除的偏离 → 在 `redlines.yaml` 的 `exceptions` 登记（`scope` + `match` + `reason` + `owner` + `review_by`），
   检查器降级为提示、过期自动转红。**只写进文档不提例外，等于没登记**；
8. 新增红线 → 先在本体仓实现检查并在 `IMPLEMENTED_REDLINES` 登记，再写进本仓 `redlines.yaml`；
   只写 YAML 不写实现会被 E301 判为"纸面红线"；
9. 能力的 `owner` 是责任锚点：改 owner 必须确认该服务确实持有这个能力（E112），并重新生成 CODEOWNERS。

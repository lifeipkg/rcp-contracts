# rcp-contracts · 契约仓

平台声明层真源。**契约先行**：任何跨服务的契约、字段、服务名、端口变更，先在本仓立，消费仓再升钉同步。

## 目录

| 路径 | 是什么 |
|---|---|
| `registry/services.yaml` | 服务登记：名称、端口、owner、能力、依赖、健康检查、挂的契约。也是 `baseline_stack` 版本真源 |
| `contracts/openapi/*.yaml` | 各服务对外 HTTP 契约（OpenAPI 3.0.3） |
| `contracts/schemas/*.yaml` | 跨服务共享结构（决策、结论、事件），禁止各服务内联复制 |
| `vocabulary/terms.yaml` | 平台立名词汇表，新概念先立名 |
| `ontology/constraints/redlines.yaml` | 可机械检查的架构红线（RL-001 ~ RL-006） |
| `tools/contract_check.py` | 契约→实现 机械对表（OpenAPI 路由 ↔ Spring 路由，两向差集） |
| `.github/workflows/java-service.yml` | 共享 CI 模板，Java 服务仓 `workflow_call` 复用 |

## 常用命令

```bash
# 版本真源
grep -A6 '^baseline_stack:' registry/services.yaml

# 契约→实现对表（在实现仓根目录跑，差集非空即未闭合）
python ../rcp-contracts/tools/contract_check.py \
  --repo . --contract ../rcp-contracts/contracts/openapi/content-patrol.yaml

# 登记/契约/红线一致性（需本体仓）
python ../rcp-ontology/rcp_ontology/cli.py check --contracts .
```

## 变更纪律

1. 改契约 → 先改本仓 → 消费仓升钉 → CI 对表闭合；
2. 新增服务 → 先登记 `services.yaml`，再挂契约，最后写实现（否则 RL-006 红）；
3. 改决策等级 → 只改 `contracts/schemas/decision.yaml` 与 `rcp-core` 的 `Decision`，两侧必须逐字一致（RL-003）；
4. DDL 不进本仓，也不进业务仓，只进 `rcp-ops/migrations`（RL-004）。

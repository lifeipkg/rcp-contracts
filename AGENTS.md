# AGENTS.md · rcp-contracts

本仓规则。工作区级流程见 `<工作区根>/AGENTS.md`，本文件只写本仓特有约束。

## 本仓是什么

平台**接口契约**仓。只有 OpenAPI、跨服务共享结构、对表工具与共享 CI 模板。
服务登记、种类、能力、决策语义、红线、术语、版本钉都在 `rcp-ontology/ontology/`——
本仓不承载声明真源，只承载「服务之间长什么样」。

## 本仓硬约束

1. **只做声明，不做实现。** 本仓不出现 Java/Python 业务代码（`tools/` 的检查脚本除外），也不出现 DDL。
2. **登记先于实现。** 新服务先在 `rcp-ontology/ontology/abox/services.ttl` 登记并在此挂契约，
   实现仓才允许开工；未登记即 RL-006 红。
3. **改契约必须与消费仓同批升钉。** 契约变更单独提交（`contract:` 前缀），消费仓的 `core-ref` / 契约引用随同一次变更更新，不允许契约先漂、实现后补。
4. **偏离必须登记，不能只在文档里说明。** 无法立即消除的违线放在
   `rcp-ontology/ontology/policy/redlines.ttl` 的例外个体里，写全
   `rcp:scope`/`rcp:match`/`rcp:reason`/`rcp:owner`/`rcp:reviewBy`；否则检查器照常判红。

5. **`decision.yaml` 是生成物。** 改决策等级只改本体仓的 `tbox/decisions.ttl`，
   然后 `render-schema` 重生成。手改会被 RL-003 判红。

## 验证

```bash
# 1) YAML 严格解析（重复键即失败，PyYAML 默认会静默取后者）
python ../rcp-ops/tools/check_manifests.py .

# 2) 本体一致性（登记 / 契约 / 红线 / 仓布局）
python ../rcp-ontology/rcp_ontology/cli.py check --contracts . -w ..

# 3) 契约层静态检查（$ref / 决策未内联 / 与基线无破坏性变更）
python tools/contract_lint.py --contracts . --baseline origin/main

# 4) 契约仓测试（含反向用例：每条检查都要能抓到违反）
python -m pytest -q tests

# 5) 契约 → 实现 对表
python tools/contract_check.py --repo ../rcp-content-patrol --contract contracts/openapi/content-patrol.yaml

# 6) 决策 schema 与真源一致（生成物被手改即红）
python ../rcp-ontology/rcp_ontology/cli.py check --contracts . -w ..
```

六条都过才算闭合。差集非空时**报告缺口清单**，不允许改契约迎合实现（那等于把 bug 写进真源）。

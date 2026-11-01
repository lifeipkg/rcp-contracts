# AGENTS.md · rcp-contracts

本仓规则。工作区级流程见 `<工作区根>/AGENTS.md`，本文件只写本仓特有约束。

## 本仓是什么

平台**声明层真源**。所有跨服务契约、服务登记、词汇、架构红线都在这里，实现仓只能消费不能私改。

## 三条本仓硬约束

1. **只做声明，不做实现。** 本仓不出现 Java/Python 业务代码（`tools/` 的检查脚本除外），也不出现 DDL。
2. **登记先于实现。** 新服务先登记 `registry/services.yaml` 并挂契约，实现仓才允许开工；未登记即 RL-006 红。
3. **改契约必须与消费仓同批升钉。** 契约变更单独提交（`contract:` 前缀），消费仓的 `core-ref` / 契约引用随同一次变更更新，不允许契约先漂、实现后补。

## 验证

```bash
python -c "import yaml,glob; [yaml.safe_load(open(f,encoding='utf-8')) for f in glob.glob('**/*.yaml',recursive=True)]"
python ../rcp-ontology/rcp_ontology/cli.py check --contracts .
python tools/contract_check.py --repo ../rcp-content-patrol --contract contracts/openapi/content-patrol.yaml
```

三条都过才算闭合。差集非空时**报告缺口清单**，不允许改契约迎合实现（那等于把 bug 写进真源）。

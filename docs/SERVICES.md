# 平台服务目录（由 rcp-ontology 渲染，勿手改）
#
# 真源：rcp-ontology/ontology/abox/services.ttl（服务/库/边）、abox/platform.ttl（基座版本钉）。
# 改登记请改 TTL 后重跑 checker/cli.py render；本文件不是声明真源。

基座版本：gin 1.10.0 / go 1.22

## 服务

| 服务 | 种类 | 端口 | 对外 | 能力 | 关系 |
|---|---|---|---|---|---|
| `api-gateway` | 网关 | 8080 | 是 | — | calls→iam |
| `contracts` | 元仓 | — | 否 | — | — |
| `dataway` | 数据网关 | 8090 | 否 | 模板写入、声明式查询 | — |
| `db-ops` | 数据库操作服务 | 8091 | 否 | 迁移执行、版本台账 | — |
| `iam` | 身份与访问管理 | 8085 | 否 | 身份认证、用户与角色 | calls→dataway、queries→dataway、writes→dataway |
| `ontology` | 元仓 | — | 否 | — | — |
| `ops` | 元仓 | — | 否 | — | — |
| `web` | 前端 | 5173 | 是 | 运营控制台 | calls→api-gateway |

## 库

| 库 | 坐标 | 能力 |
|---|---|---|


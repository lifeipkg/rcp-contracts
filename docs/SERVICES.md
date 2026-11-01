# 平台服务目录（由 rcp-ontology 渲染，勿手改）

基座版本：{'java': '17', 'spring_boot': '3.3.5', 'maven_surefire': '3.2.5'}

## 服务

| 服务 | 种类 | 端口 | 对外 | 能力 | 依赖 |
|---|---|---|---|---|---|
| `api-gateway` | 网关 | 8080 | 是 | 巡查派发、巡查线自描述 | content-patrol、message-patrol、account-patrol、fund-patrol |
| `content-patrol` | 巡查线 | 8081 | 否 | 内容判重 | — |
| `message-patrol` | 巡查线 | 8082 | 否 | 消息命中 | — |
| `account-patrol` | 巡查线 | 8083 | 否 | 账号规则 | — |
| `fund-patrol` | 巡查线 | 8084 | 否 | 资金规则 | — |
| `dataway` | 数据网关 | 8090 | 否 | 声明式查询、模板写入 | — |
| `db-ops` | 数据库操作服务 | 8091 | 否 | 迁移执行、版本台账 | — |
| `web` | 前端 | 5173 | 是 | 运营控制台 | api-gateway |

## 库

| 库 | 坐标 | 能力 |
|---|---|---|
| `rcp-core` | `com.risk.platform:rcp-core:1.0.0` | 决策模型、巡查流水线、规则引擎 |

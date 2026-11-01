# 服务发现：形态已就位，接线未完成

本文件记录平台在"不写死上游地址"这件事上的当前状态、为什么停在这里、以及接线的确切步骤。
现状用一句话概括：**声明与基础设施已就位，应用侧未接入，因此 RL-007 以例外形式存在。**

## 状态

| 项 | 状态 | 位置 |
|---|---|---|
| 服务发现声明 | 已完成 | `registry/services.yaml` 的 `discovery` 段，`state: declared` |
| 红线与例外登记 | 已完成 | `ontology/constraints/redlines.yaml` 的 `RL-007` 与 `exceptions` |
| 本地编排基础设施 | 已完成 | `rcp-ops/docker-compose.yml` 的 `nacos` 服务 |
| 集群清单基础设施 | 已完成 | `rcp-ops/k8s/05-nacos.yaml`，已进 `kustomization.yaml` |
| 部署侧配置注入 | **不需要** | 应用侧占位符默认值即命中 Service 名（见接线第 3 步），K8s 与 compose 均不注入 |
| 应用侧 discovery 依赖 | **未完成** | 各 Java 服务 `pom.xml` 与 `application.yml` |
| 网关按服务名寻址 | **未完成** | 仍读 `PATROL_ROUTES_ENDPOINTS_*` |

> 曾加过 `NACOS_SERVER` / `NACOS_NAMESPACE` / `NACOS_GROUP` 三个配置锚点（configmap 与 api-gateway 各一份），
> 已删除：应用代码不读它们，占位符默认值已够用，留着只会变成两份对不上的真源。
> 只有换 namespace、跨集群部署或启用鉴权时才需要注入，届时与本表上一行一起改。

## 为什么停在这里

三条都是硬约束，不是取舍：

1. **依赖不可验证。** 本机无 `mvn` 可执行文件，`~/.m2` 内也没有 `com.alibaba.cloud` 的构件。
   改动 pom 后无法编译，等于提交一个未验证的运行行为变更。
2. **无集群可标定。** 本工作区没有真实集群，注册中心接入的正确性（注册延迟、健康检查、
   名称解析失败时的降级）无法观测。写"已接入"就是自述，不是事实。
3. **干扰面大。** 接入会同时改 7 个服务仓的 pom 与配置，属高风险轨道，需要独立复核记录；
   在没有可验证环境时一次铺开，失败面会覆盖整个平台。

因此选择：**先把可机械验证的部分做满**（声明、清单、红线、例外、复审期限），
把不可验证的部分明确标注为未完成，而不是假装完成。

## 当前偏离的具体形态

`rcp-ops` 的 compose 与 K8s 清单里仍有 12 处指向内部服务的地址：

```
PATROL_ROUTES_ENDPOINTS_CONTENT: http://content-patrol:8081
PATROL_ROUTES_ENDPOINTS_MESSAGE: http://message-patrol:8082
PATROL_ROUTES_ENDPOINTS_ACCOUNT: http://account-patrol:8083
PATROL_ROUTES_ENDPOINTS_FUND: http://fund-patrol:8084
```

这些地址由 Docker DNS 或 K8s Service 解析，扩缩容时不需要改配置，**但新增服务或改端口时必须改**，
且消费方无法在未知上游存在时自动发现。这正是 RL-007 要拦的东西，所以它们以例外形式存在：

```yaml
exceptions:
  - redline: RL-007
    scope: "rcp-ops/**"
    match: "http://(content|message|account|fund)-patrol:\\d+"
    review_by: 2026-12-31
```

例外的作用不是"免检"，而是把偏离变成**有主、有期限、可机械复查**的状态：

- 命中例外 → 降级为 `warn`，仍会打印文件与行数
- 同一例外命中多行 → 聚合成一条，不刷屏
- `review_by` 过期 → 自动恢复 `error`
- 未登记的同类地址 → 直接 `error`，不会被例外连带放过

## 接线步骤

按顺序做，每步都有可复算的验收。

1. **钉版本。** 在 `registry/services.yaml` 的 `baseline_stack` 增补
   `spring_cloud_alibaba: "<钉住的具体版本>"`。此文档不写具体版本号，因为尚未验证兼容性；
   写入未经验证的版本比留空更糟。
2. **加依赖。** 7 个 Java 服务仓的 `pom.xml` 加
   `com.alibaba.cloud:spring-cloud-starter-alibaba-nacos-discovery`，版本引用上一步的 property。
3. **加配置。** 各服务 `application.yml`：

   ```yaml
   spring:
     cloud:
       nacos:
         discovery:
           server-addr: ${NACOS_SERVER:nacos:8848}
           namespace: ${NACOS_NAMESPACE:risk-control}
           group: ${NACOS_GROUP:DEFAULT_GROUP}
   ```

4. **改寻址。** 网关改为按服务名解析上游；`PATROL_ROUTES_ENDPOINTS_*` 若保留，只作为覆盖率覆盖项，
   不再是唯一来源。
5. **收尾。** 删除 `discovery.state: declared` 改为 `wired`；删除 `redlines.yaml` 里的 RL-007 例外；
   删除 compose 与 configmap 中的四条上游地址。

### 验收命令

```bash
# 本体 + 红线（含 repo-layout 级）
python rcp-ontology/rcp_ontology/cli.py check --contracts rcp-contracts --workspace .

# 契约层（引用可解析 / 决策未内联 / 与基线无破坏性变更）
python rcp-contracts/tools/contract_lint.py --contracts rcp-contracts --baseline origin/main
```

预期结果：第 5 步完成后，第一条命令应为 **0 错误 0 提示**；只要还有 RL-007 的 `warn`，
就说明例外仍在生效，接线尚未完成。这是判断"是否真的接完了"的机械依据，不看自述。

## 未覆盖

- 注册中心自身的高可用与持久化：`05-nacos.yaml` 是单副本 standalone，只给形态。
- 配置中心能力：当前只声明 discovery，未启用 config。若要把 `01-configmap.yaml` 的配置迁到
  Nacos config，需另立 `config` 段与迁移步骤。
- 名称解析失败时的降级语义：属于运行行为，须在有集群后标定，此处不预设。

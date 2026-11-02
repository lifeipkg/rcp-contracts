# 服务发现：形态已就位，接线未完成

本文件记录平台在"不写死上游地址"这件事上的当前状态、为什么停在这里、以及接线的确切步骤。
现状用一句话概括：**声明与基础设施已就位，应用侧未接入，因此 RL-007 以例外形式存在。**

## 状态

| 项 | 状态 | 位置 |
|---|---|---|
| 服务发现声明 | 已完成 | `registry/services.yaml` 的 `discovery` 段，`state: declared`（见下文"为何停在 declared"） |
| 基线版本钉定 | 已完成 | `baseline_stack` 增补 `spring_cloud: 2023.0.3`、`spring_cloud_alibaba: 2023.0.3.4`，经 Maven 构建验证可解析 |
| 红线与例外登记 | 已完成 | `ontology/constraints/redlines.yaml` 的 `RL-007` 与 `exceptions` |
| 本地编排基础设施 | 已完成 | `rcp-ops/docker-compose.yml` 的 `nacos` 服务 + `nacos-init`（一次性创建 risk-control namespace） |
| 集群清单基础设施 | 已完成 | `rcp-ops/k8s/05-nacos.yaml`，已进 `kustomization.yaml` |
| 应用侧 discovery 依赖 | **已接线（编译+测试验证）** | 7 个 Java 服务 `pom.xml` 引入 `spring-cloud-starter-alibaba-nacos-discovery`，`application.yml` 按 `${NACOS_SERVER:nacos:8848}` 占位符配置；`@SpringBootTest` 显式关闭 discovery（测试环境无注册中心） |
| 网关按服务名寻址 | **已实现（单测验证）** | `HttpPatrolClient` 先查 `DiscoveryClient`（多实例轮转），注册中心不可用或无实例时回落 `patrol.routes.endpoints`（过渡期仍可由 `PATROL_ROUTES_ENDPOINTS_*` 覆盖，不再是唯一来源） |
| 运行时标定 | **未完成** | compose 起全平台验证注册与路由（本机 Docker daemon 被安全策略阻止启动） |
| 收尾 | **未完成** | 标定通过后：`discovery.state` 改 `wired`、删 RL-007 例外、删 compose/configmap/10-api-gateway.yaml 中 12 处写死地址 |

> 部署侧配置注入不需要：占位符默认值即命中 Service 名（compose 服务名与 K8s Service 名均为
> nacos）。唯一例外是 namespace 必须存在——compose 用 `nacos-init` 幂等创建，K8s 部署时需
> 同样保证（可加 Job，随收尾一并处理）。
> 曾加过 `NACOS_SERVER` / `NACOS_NAMESPACE` / `NACOS_GROUP` 三个配置锚点（configmap 与 api-gateway 各一份），
> 已删除：应用代码占位符默认值已够用，留着只会变成两份对不上的真源。

## 为什么停在这里

三条硬约束的当前状态：

1. ~~依赖不可验证~~ **已解除**：本机已装便携 JDK 17 + Maven 3.9.16（`.workbuddy/tools/`），
   7 个服务 `mvn test` 全部通过，SCA 2023.0.3.4 依赖解析与编译验证完成。
2. **无运行时可标定。** 本机 Docker daemon 被安全策略阻止启动（wsl.exe 在黑名单），
   compose 标定（注册、按名解析、多实例轮转、失败降级）无法执行。解锁后跑
   `docker compose up --build`，按下方验收命令复核。
3. **收尾仍需独立复核。** 标定通过后才改 `wired`、删例外、删写死地址——在那之前
   `state: declared` + RL-007 例外继续如实反映"接线已提交、运行行为未标定"的状态。

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

按顺序做，每步都有可复算的验收。第 1-4 步已完成并提交，第 5 步待运行时标定。

1. ~~**钉版本。**~~ 已完成：`baseline_stack` 钉 `spring_cloud: "2023.0.3"`、
   `spring_cloud_alibaba: "2023.0.3.4"`（与 Boot 3.3.5 兼容，Maven 构建验证）。
2. ~~**加依赖。**~~ 已完成：7 个 Java 服务仓的 `pom.xml` 引入
   `com.alibaba.cloud:spring-cloud-starter-alibaba-nacos-discovery`（版本由 BOM 管理）。
3. ~~**加配置。**~~ 已完成：各服务 `application.yml`：

   ```yaml
   spring:
     cloud:
       nacos:
         discovery:
           server-addr: ${NACOS_SERVER:nacos:8848}
           namespace: ${NACOS_NAMESPACE:risk-control}
           group: ${NACOS_GROUP:DEFAULT_GROUP}
   ```

4. ~~**改寻址。**~~ 已完成：`HttpPatrolClient` 先经 `DiscoveryClient` 按注册名解析
   （`patrol.routes.services`，多实例轮转），注册中心不可用或无实例时回落
   `patrol.routes.endpoints`；`PATROL_ROUTES_ENDPOINTS_*` 保留为覆盖/兜底项，
   收尾后部署侧不再注入。新增 `HttpPatrolClientTest` 覆盖发现优先、多实例轮转、
   无注册中心回落、注册中心异常回落、未知巡查线拒绝五条路径。
5. **收尾（待标定通过）。** `discovery.state` 改 `wired`；删除 `redlines.yaml` 里的 RL-007 例外；
   删除 compose、configmap 与 `10-api-gateway.yaml` 中的四条上游地址（共 12 处）。

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

# 服务发现：接线完成（Nacos，demo 定位）

本文件记录平台在"不写死上游地址"这件事上的最终状态、接线过程与验收依据。
现状用一句话概括：**声明、依赖、配置、寻址、清单全部就位并提交，RL-007 无例外，0 偏离；
平台为 demo 定位，运行时行为未做真实标定，以编译、单测与机械检查为验收依据。**

## 状态

| 项 | 状态 | 位置 |
|---|---|---|
| 服务发现声明 | 已完成 | `rcp-ontology/ontology/abox/platform.ttl` 的 `rcp:discovery` 结构，`rcp:discoveryState "wired"` |
| 基线版本钉定 | 已完成 | `rcp-ontology/ontology/abox/platform.ttl` 的 `rcp:stack`：`spring_cloud: "2023.0.3"`、`spring_cloud_alibaba: "2023.0.3.4"`（Maven 构建验证与 Boot 3.3.5 兼容）；版本真源已随纯 TTL 重构从契约仓迁至本体仓 |
| 红线 | 已完成 | RL-007 生效中，`policy/redlines.ttl` 的「例外登记」为空，无任何例外 |
| 本地编排基础设施 | 已完成 | `rcp-ops/docker-compose.yml` 的 `nacos` 服务 + `nacos-init`（一次性幂等创建 risk-control namespace） |
| 集群清单基础设施 | 已完成 | `rcp-ops/k8s/05-nacos.yaml`，已进 `kustomization.yaml` |
| 应用侧 discovery 依赖 | 已接线（仅 Java 侧） | 5 个 Java 服务（api-gateway 与四条巡查线）`pom.xml` 引入 `spring-cloud-starter-alibaba-nacos-discovery`，`application.yml` 按 `${NACOS_SERVER:nacos:8848}` 占位符配置；`@SpringBootTest` 显式关闭 discovery（测试环境无注册中心）。3 个 Go 服务（iam/dataway/db-ops）**不接 Nacos**：按部署侧 Service 名经 DNS 解析（`rcp:fallback` 即 `k8s-dns`），清单同样不写上游 URL |
| 网关按服务名寻址 | 已实现 | `HttpPatrolClient` 先查 `DiscoveryClient`（多实例轮转），注册中心不可用或无实例时回落 `patrol.routes.endpoints`（本地默认值，部署侧不再注入环境变量）；IAM 的鉴权与透传共用 `IamAddressResolver`（发现优先、`iam.routes.endpoint` 兜底） |
| 清单写死地址 | 已清除 | compose、`01-configmap.yaml`、`10-api-gateway.yaml` 中共 12 处 `PATROL_ROUTES_ENDPOINTS_*` 全部删除 |
| 运行时标定 | 未执行（demo 定位，不要求） | 平台不真实运行；若后续需要，起 compose（或本机 Nacos standalone + 5 个 jar + 3 个 Go 二进制）按下方验收复核 |

> 部署侧配置注入不需要：占位符默认值即命中 Service 名（compose 服务名与 K8s Service 名均为
> nacos）。唯一前提是 namespace 必须存在——compose 用 `nacos-init` 幂等创建；K8s 部署时需
> 同样保证（可加一次性 Job）。
> 曾加过 `NACOS_SERVER` / `NACOS_NAMESPACE` / `NACOS_GROUP` 三个配置锚点（configmap 与 api-gateway 各一份），
> 已删除：应用代码占位符默认值已够用，留着只会变成两份对不上的真源。

## 接线过程（5 步，全部完成）

1. **钉版本。** 在 `rcp-ontology/ontology/abox/platform.ttl` 的 `rcp:stack` 钉
   `spring_cloud: "2023.0.3"`、`spring_cloud_alibaba: "2023.0.3.4"`（nacos-client 2.4.x，配 Nacos Server v2.3.2）。
2. **加依赖。** 5 个 Java 服务仓的 `pom.xml` 引入
   `com.alibaba.cloud:spring-cloud-starter-alibaba-nacos-discovery`（版本由 BOM 管理）。
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

4. **改寻址。** `HttpPatrolClient` 先经 `DiscoveryClient` 按注册名解析
   （`patrol.routes.services`，多实例轮转），注册中心不可用或无实例时回落
   `patrol.routes.endpoints`。新增 `HttpPatrolClientTest` 覆盖发现优先、多实例轮转、
   无注册中心回落、注册中心异常回落、未知巡查线拒绝五条路径。
5. **收尾。** `rcp:discoveryState` 改 `"wired"`；删除 `policy/redlines.ttl` 的 RL-007 例外；
   删除 compose、configmap 与 `10-api-gateway.yaml` 中的 12 处写死地址。

### 验证依据

- **编译与单测**：便携 JDK 17 + Maven 3.9.16 下 5 个 Java 服务 `mvn test` 全部通过（70 条测试；
  该基线采集于 IAM 接入前，且 dataway/db-ops 已迁 Go，计数按当前 Java 服务数）。
  Go 服务（iam/dataway/db-ops）以 `go vet` / `go test` / `go build` 验收，不经 Maven。
- **机械检查**：下方验收命令应输出 **0 错误 0 提示**——这是"清单里真的没有写死地址、
  例外真的删了"的机械依据，不看自述。
- **运行时行为**（注册延迟、按名解析、失败降级的实测）：demo 定位下未执行。
  网关的降级语义已由单测覆盖（注册中心异常/无实例时回落配置地址，巡查线不可用转加审），
  真实环境的数值标定留待有集群时进行。

### 验收命令

```bash
# 本体 + 红线（含 repo-layout 级）
python rcp-ontology/checker/cli.py check --contracts rcp-contracts --workspace .

# 契约层（引用可解析 / 决策未内联 / 与基线无破坏性变更）
python rcp-contracts/tools/contract_lint.py --contracts rcp-contracts --baseline origin/main
```

预期结果：**0 错误 0 提示**。若出现 RL-007 相关输出，说明有新的写死地址混入或例外被重新登记。

## 未覆盖

- 注册中心自身的高可用与持久化：`05-nacos.yaml` 是单副本 standalone，只给形态。
- 配置中心能力：当前只声明 discovery，未启用 config。若要把 `01-configmap.yaml` 的配置迁到
  Nacos config，需另立 `config` 段与迁移步骤。
- K8s 侧 namespace 初始化 Job：compose 有 `nacos-init`，K8s 清单暂无对应 Job，
  部署时需保证 namespace `risk-control` 先于服务存在。
- **Go 服务的发现能力**：iam/dataway/db-ops 不注册 Nacos，只靠 K8s Service DNS 解析，
  因此没有注册中心侧的实例健康视图与摘流能力。若将来 dataway 需要多实例轮转或被网关
  按注册名调用，要先为 Go 侧接 `nacos-sdk-go`，并把 `rcp:discoveryState` 的语义按
  "Java 注册 / Go 不注册"这段差异重新表述——当前 `"wired"` 只对 Java 侧成立。
- 运行时数值标定（注册延迟、健康检查、降级阈值）：见上，demo 定位下不预设。

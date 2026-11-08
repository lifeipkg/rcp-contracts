# 服务发现：K8s Service DNS（无注册中心）

本文件记录平台在"不写死上游地址"这件事上的最终状态与验收依据。

现状一句话：**不接注册中心。8 个仓全部 Go，服务间寻址只靠部署侧的 Service 名 + 端口，
经 DNS 解析；多实例负载由 k8s Service / compose DNS 承担，网关自己做轮转的逻辑已删除。**

## 状态

| 项 | 状态 | 位置 |
|---|---|---|
| 服务发现声明 | 已收敛 | `rcp-ontology/ontology/abox/platform.ttl` 的 `rcp:discovery`：`discoveryKind "k8s-dns"`，无 `server` / `discoveryGroup` |
| 基线版本钉定 | 已收敛 | 同文件 `rcp:stack`：只剩 `go "1.22"` / `gin "1.10.0"`；Java 相关版本钉随巡查线一并移除 |
| 红线 | 生效中 | RL-007：部署清单不得写死内部服务地址；`policy/redlines.ttl` 的例外登记为空 |
| 注册中心基础设施 | **已删除** | `rcp-ops/k8s/05-nacos.yaml`、compose 的 `nacos` / `nacos-init` 已移除；`kustomization.yaml` 不再引用 |
| 应用侧发现依赖 | 无 | 没有任何仓引注册中心 SDK；Go 服务从环境变量取「服务名 + 端口」拼基础地址 |
| 网关寻址 | 已实现 | `internal/config` 从 `IAM_HOST` / `IAM_PORT` 取值（默认 `localhost:8085`），部署时传 Service 名 `iam` |
| IAM 寻址 dataway | 已实现 | `DATAWAY_HOST` / `DATAWAY_PORT`，同一形态 |
| 清单写死地址 | 已清除 | 清单只出现服务名与端口，不出现 `http://<内部服务>:<端口>` |

## 为什么不用注册中心

原先接 Nacos 是为了让四条 Java 巡查线能被网关按注册名发现。四条线随方向调整一并下线后，
注册中心的唯一消费者消失：剩下的 4 个服务（api-gateway / iam / dataway / db-ops）调用关系是
固定扇出（网关 → IAM → dataway），没有"运行时才知道有哪些实例"的需求。

于是收敛为最朴素的一层：**部署侧给名字，DNS 给地址，Service 做负载均衡**。
少一个组件就少一套 HA、namespace 初始化与配置真源。

## 寻址形态

```bash
# 网关 → IAM
IAM_HOST=iam IAM_PORT=8085

# IAM → dataway
DATAWAY_HOST=dataway DATAWAY_PORT=8090
```

代码侧只做一件事：`http://$HOST:$PORT`。没有注册、没有心跳、没有实例列表，
也没有"注册中心挂了回落 endpoints"那条降级链——**不需要，因为不存在注册中心**。

## 与旧形态的差异（破坏性，已获准）

| 项 | 旧 | 现在 |
|---|---|---|
| 发现机制 | Nacos 注册 + `DiscoveryClient` 按名解析 | 无注册中心，Service DNS |
| 多实例分发 | 网关侧轮转各实例 | k8s Service / compose DNS |
| 降级链 | 注册中心不可用 → 回落 `endpoints` | 无（地址直接来自部署侧注入） |
| 配置锚点 | `NACOS_SERVER` / `NACOS_NAMESPACE` / `NACOS_GROUP` | 无 |

## 验收命令

```bash
# 本体 + 契约 + 红线（含 repo-layout 级）
python rcp-ontology/checker/cli.py check --ontology rcp-ontology --contracts rcp-contracts -w . --require-workspace

# 契约层（引用可解析 / 与基线无破坏性变更）
python rcp-contracts/tools/contract_lint.py --contracts rcp-contracts --baseline origin/main
```

预期：**0 错误 0 提示**。若出现 RL-007 相关输出，说明有新的写死地址混入或例外被重新登记。

## 未覆盖

- 真实集群上的 DNS 解析行为：平台为 demo 定位，不真实部署，以检查器与单测为验收依据。
- 跨集群 / 多 Zone 的服务寻址：当前只覆盖单集群内的 Service 名。
- 若将来真的需要注册中心（例如动态扩容的多上游节点），要先在 `abox/platform.ttl` 改
  `rcp:discovery`，再补应用侧 SDK 与清单——不要只改代码不改声明。

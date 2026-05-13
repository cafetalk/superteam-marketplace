# RPC、API、GraphQL

t-rex 后端三种"对外暴露"形态并存：Dubbo（服务间）/ REST + OpenAPI Delegate（对外）/ GraphQL（查询层）。本章规约各自用法与边界。

## Dubbo【强制】

**用途**：t-rex 后端**服务间**通信的主要 RPC 协议。

**接口约定**：
- Dubbo 接口必须放在工程的 `api` / `*-api` 模块（不能放在 service 模块）
- 接口命名以 `Remote` 开头 + `Service` 结尾：`Remote<Domain>Service`
- 接口及其参数 / 返回值的 POJO **必须可序列化**（实现 `Serializable` 或符合 Dubbo 默认序列化协议）
- 接口方法不抛 checked exception；业务异常通过统一返回包装承载（见 `07-exception-and-logging.md`）

**示例**（drex-core/core-api 已落地）：
```java
// xyz.trex.<project>.api.RemoteCampaignService
public interface RemoteCampaignService {
    CampaignDetail getCampaign(Long campaignId);
    List<CampaignSummary> listCampaigns(CampaignQueryRequest request);
}
```

**消费方**：在 POM 引入 `<project>-api` 依赖即可（不需要拉整个服务）。

## OpenAPI + Delegate 模式【强制】（Gateway 形态）

**用途**：trex-web 风格的 Gateway 工程对外 REST API。

**流程**：
1. 维护 OpenAPI 3 规范文件（`*.yaml`）
2. Maven 构建期用 OpenAPI generator 生成 Controller 接口（`*ApiController`）+ Delegate 接口（`*ApiDelegate`）
3. 业务代码写在 **`*ApiDelegateImpl`**（自己写的实现类），**不写在 Controller**
4. Controller 自动注入 Delegate 实现

**类命名**：
- 生成的：`CampaignApiController` + `CampaignApiDelegate`
- 自己写的：`CampaignApiDelegateImpl`

**反例**：
```text
❌ 直接修改 generator 产物（每次构建被覆盖）
❌ 在 *ApiController 里写业务逻辑
❌ 把 OpenAPI schema 当成只能"反向同步"的文档（应当 schema-first：先改 yaml 再生成代码）
```

> 规则一句话：**业务一定写在 `*ApiDelegateImpl`，不写在生成产物里。**

TODO(@allen)：OpenAPI 规范文件的存放位置 + 团队协作流程（PRD → schema → 生成）。

## GraphQL（查询层）

**用途**：drex-core 的 `core-graphql` 模块提供 GraphQL 查询入口，主要面向**复杂查询**场景（多表关联 / 嵌套字段 / 客户端按需取字段）。

**技术栈**：
- `spring-boot-starter-graphql`
- `graphql-java-extended-scalars` 22.0
- 数据访问层：MyBatis-Plus mappers（位于 `core-graphql/mapper/`）

**何时用 GraphQL**：
- 列表 / 详情查询字段很多，客户端不同场景按需取
- 多领域聚合查询，避免多次 HTTP / RPC 往返

**何时不用 GraphQL**：
- 简单 CRUD → 用 REST / Dubbo
- 写操作 / 命令式接口 → 用 REST / Dubbo（GraphQL mutation 在 t-rex 暂不推广）

## 三种形态选型决策

```text
你的接口对外吗？
├── 是
│   ├── 是「读多 + 字段多 + 客户端按需」 → GraphQL
│   └── 否                              → REST (OpenAPI Delegate)
└── 否（仅供其他后端服务调用）           → Dubbo (Remote*Service)
```

TODO(@allen)：跨服务事件 / 消息（MQ）的位置 — 何时用 MQ vs Dubbo？

## 维护

- 新增 Dubbo 接口必须更新消费方 POM 依赖版本
- OpenAPI schema 变更走 PR 审核（接口契约）
- GraphQL schema 变更需评估对前端 / SDK 的影响

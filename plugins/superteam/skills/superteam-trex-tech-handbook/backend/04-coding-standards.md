# 编码规范

参考蓝本：阿里巴巴 Java 开发手册（黄山版）。本章记录 t-rex 与之**有差异或补充**的规约；未列出的部分**默认沿用阿里手册**。

## 包名规则【强制】

t-rex 后端包名规则**双轨**：

| 项目类型 | groupId / 包前缀 | 说明 |
|---|---|---|
| 新工程（2026-05 起新建） | `xyz.trex.*` | 统一前缀；示例 `xyz.trex.<project>.<layer>` |
| 老工程 | `com.drex.*` | **保持不变，不强制迁移** |

**已知老工程**（保持 `com.drex.*`）：
- `drex-core`（含 `com.drex.core.web` / `com.drex.core.service` / `com.drex.core.dal` / `com.drex.core.api` / 等）
- `drex-passport`
- `trex-web`（虽叫 trex-web，groupId 仍是 `com.drex`）
- TODO(@allen)：补完整老工程清单

**新工程示例**：

```text
xyz.trex.<project>
├── api          # Dubbo Remote* 接口
├── model        # 数据对象 / DTO / VO
├── dal          # 数据访问层
├── service      # 业务逻辑
├── web          # REST 入口（如适用）
└── ...
```

**正例**：
```text
✅ xyz.trex.campaign.api.RemoteCampaignService    （新工程 Dubbo 接口）
✅ com.drex.core.service.CampaignServiceImpl      （老工程 drex-core，保持不变）
```

**反例**：
```text
❌ com.trex.* / com.drex.trex.* / cn.drex.* 等混用前缀
❌ 新工程用 com.drex.*（除非确为老工程的延伸模块）
```

`〔t-rex 现状〕`：**共享库 / 二方库**归属哪个前缀？— TODO(@allen) 待定规则：
- 选项 A：跟随宿主工程（共享库可能有两份）
- 选项 B：统一归 `xyz.trex.common.*`
- 选项 C：保留 `com.drex.shared.*` 作历史共享库

## 类名后缀【强制】

| 后缀 | 含义 | 示例 |
|---|---|---|
| `*Controller` | Spring REST 入口 | `CampaignController` |
| `*Service` | 业务逻辑接口 | `CampaignService` |
| `*ServiceImpl` | 业务逻辑实现 | `CampaignServiceImpl` |
| `*Mapper` | MyBatis-Plus 数据映射 | `CampaignMapper` |
| `*MapperStruct` | MapStruct 对象转换（注意与 `*Mapper` 区分） | `CampaignMapperStruct` |
| `*DTO` | 服务间 / 跨层数据传输对象 | `CampaignDTO` |
| `*VO` | 视图层值对象 | `CampaignDetailVO` |
| `*Request` / `*Response` | API 请求 / 响应包装 | `CampaignCreateRequest` / `CampaignListResponse` |
| `*ApiDelegateImpl` | OpenAPI generator 生成的 Controller 的业务委托 | `CampaignApiDelegateImpl` |
| `Remote*Service` | Dubbo 远程服务接口（一律放 `api` 模块） | `RemoteCampaignService` |

**正例**：
```text
✅ CampaignService + CampaignServiceImpl
✅ CampaignMapper (MyBatis) 与 CampaignMapperStruct (MapStruct) 并存
✅ RemoteAdvertiserIntelligenceService (drex-core/core-api 内已落地)
```

**反例**：
```text
❌ CampaignSvc / CampaignSer / CampaignMgr （非标准缩写后缀）
❌ Mapper 既做 MyBatis 又做对象转换 → 必须拆成 *Mapper + *MapperStruct
❌ Remote* 接口放在 service 模块 → 必须在 api 模块（供消费者依赖）
```

## 阿里手册其余规约

下列章节**沿用阿里 Java 开发手册（黄山版）**，本 handbook 不重复列出，仅标注 t-rex 偏离点：

- 命名风格：阿里规约 + 上面的后缀约定
- 常量定义、代码格式：完全沿用
- OOP 规约：完全沿用
- 集合处理、并发处理：完全沿用
- 控制语句：完全沿用
- 注释规约：完全沿用（建议引入 p3c-pmd 自动检查）

**工具集成**：建议 IDE 安装 **Alibaba Java Coding Guidelines (p3c)** 插件，开启自动检查。

TODO(@allen)：明确"哪些阿里规则在 t-rex 是【强制】vs【推荐】"清单。

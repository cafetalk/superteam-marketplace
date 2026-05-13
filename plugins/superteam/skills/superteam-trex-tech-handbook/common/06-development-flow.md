# 研发过程 SOP

本章把 `common/02` (分支 / commit)、`common/03` (评审)、`common/05` (Linear) 的规则**串成一条端到端流程** —— 从拿到任务到 push 评审分支，开发者每一步该做什么。

不重复 02 / 03 / 05 的严格规则；本章是**串接 + 个人 checklist**。

## 端到端 SOP【强制】

```text
[1] 任务规划 / Linear issue       (见 common/05)
       │
       ▼
[2] 设计（如需 RFC / design doc）
       │
       ▼
[3] 本地环境准备
       │
       ▼
[4] worktree + dev 分支            (见 common/02)
       │
       ▼
[5] 开发 + commit 节奏
       │
       ▼
[6] 自检 checklist (见 §自检)
       │
       ▼
[7] push review 分支 + 创建 MR     (见 common/03)
```

7 步**必须串行**走完，不允许跳步。

---

## 1. 任务规划 / Linear issue

**关键动作**：
- 立刻在 Linear 起 issue（**先建后细化**，见 `common/05` 何时建 issue 的【强制】）
- 归属正确的 Project；找不到归属归 `trex` backlog
- description 至少写 WHY + WHAT 草稿（即便都是 TBD）
- 状态：`Backlog`

`〔t-rex 现状〕` 跳过 Linear issue 直接动手是反例 —— 后续追溯断链。

---

## 2. 设计阶段

**是否需要 RFC**？判断（见 `backend/appendix/templates/rfc.md` 前言）：

| 场景 | 处理 |
|---|---|
| 跨服务 / 跨团队设计 | ✅ **必须 RFC** |
| 引入新中间件 / 新框架 | ✅ **必须 RFC** |
| API / 协议级修改 | ✅ **必须 RFC** |
| 单服务内部小特性 | 写在 `<repo>/technical_design/<日期>_<topic>/` 即可 |
| Bug 修复 / 小重构 | 不需要，commit msg + Linear comment 说明 |

**写完设计就做的事**：
- 设计文档 commit 进仓（路径：`<repo>/technical_design/...` 或 `trex-docs/`）
- 把链接贴回 Linear issue description
- Linear issue 状态从 `Backlog` → `Todo`（见 `common/05` 状态机）

---

## 3. 本地环境准备

新人 / 新机首次开发 t-rex 后端，必备清单（见 `backend/appendix/toolchain.md`）：

- [ ] **JDK 17** 安装并设为默认
- [ ] **Maven 3.6+**（仓内通常带 `mvnw` Wrapper，推荐用 wrapper）
- [ ] **IDE**: IntelliJ IDEA + 必装插件：
  - Lombok
  - **p3c-pmd**（阿里 Java 编码规约自动检查）
- [ ] 仓库 clone 到 `{your_workspace}/backend-java/<repo-name>/`（见 `common/01`）
- [ ] `~/.m2/settings.xml` 配置内部 Nexus / Aliyun Maven 仓库地址（TODO(@allen): 公布地址）
- [ ] Nacos 本地 namespace 申请 / `bootstrap.properties` 配置
- [ ] 本地 OTS / PG / Redis 桩 —— TODO(@allen): docker-compose 模板
- [ ] GitLab SSH key 已加（远端 push 用 SSH）
- [ ] 已读 `common/02` 分支 + commit 规约（必须 dogfood）

环境准备**一次性投入**，工具链版本由 `kiki-framework` parent POM 锁定。

---

## 4. worktree + dev 分支

按 `common/02-branch-and-commit.md` 创建：

```bash
cd <your_workspace>/backend-java/<repo>

# 新建 worktree + dev 分支（一步完成）
git worktree add .worktrees/dev_<YYMMDD>_<name> -b dev_<YYMMDD>_<name>

cd .worktrees/dev_<YYMMDD>_<name>
```

**name 怎么取**：
- 与 Linear issue 主题对应（短、kebab-case）
- 例 issue 是 "campaign airdrop rebuild API" → `dev_260513_campaign-airdrop-rebuild`
- 不需要带 Linear ID（见 `common/05` "代码串联"节）

Linear issue 状态 `Todo` → `In Progress`（有 dev 分支 + 第一次 commit 后）。

---

## 5. 开发与 commit 节奏

**【推荐】小步提交**：

| 反模式 | 推荐做法 |
|---|---|
| 一周一个 mega-commit | 每个可独立解释的变更一个 commit |
| commit msg 写 "wip" / "update" | 严格遵守 `common/02` prefix 枚举 |
| 单测与代码分两个 PR | 单测与对应代码同 commit 或紧跟 |
| 临时调试代码留在 commit 里 | review 前 squash / 删干净 |

**典型一次 commit 的内容粒度**：
- 一个 service 方法 + 它的单测
- 一个 endpoint + delegate 实现 + 单测
- 一次 schema 改动 + 配套 mapper
- 一次重构 + 不变行为的单测验证

**禁止在 commit 里夹**（必须拆开）：
- 与本任务无关的代码风格修整
- 升级依赖（独立 commit + 独立 review）
- 自动格式化全文件（独立 `style:` commit）

---

## 6. Code review 自检 checklist【强制】

push 评审分支前**逐项确认**，缺一项即不可 push review：

### 6.1 功能正确性
- [ ] 关键 case 本地启动跑通（含正常 / 异常分支）
- [ ] 接口契约（OpenAPI / GraphQL / Dubbo）已与上下游对接验证
- [ ] 数据库读写在本地或开发库验证

### 6.2 测试
- [ ] 新增 / 修改的 service / mapper / delegate 都有单测
- [ ] 单测全部通过：`./mvnw test`
- [ ] **不允许**为了通过测试而 mock 掉真正应该验证的逻辑
- [ ] 关键路径手工 case 已记录到提测单（见 `backend/appendix/templates/test-handoff.md`）

### 6.3 代码规范（见 `backend/04-coding-standards.md`）
- [ ] 包名前缀正确（新工程 `xyz.trex.*` / 老工程 `com.drex.*`）
- [ ] 类名后缀符合约定（`*Controller / *Service / *ServiceImpl / *Mapper / *MapperStruct / *DTO / *VO / Remote*Service / *ApiDelegateImpl`）
- [ ] 命名 / 格式 / 注释通过 p3c-pmd IDE 检查
- [ ] 模块依赖方向正确（不破 `backend/03-module-design.md` 的形态）

### 6.4 异常 / 日志（见 `backend/07-exception-and-logging.md`）
- [ ] 错误码：新加的错误用 enum，编号段位与项目约定一致
- [ ] 异常：抛 `<Project>Exception` 或经 `GlobalExceptionHandler` 包装；不直接 `throw RuntimeException`
- [ ] 日志：用 SLF4J `@Slf4j`；不用 `System.out.println` / `e.printStackTrace()`
- [ ] 敏感字段（手机号 / token / 私钥引用）已脱敏

### 6.5 安全（见 `backend/09-security.md`）
- [ ] 鉴权 / token 校验不绕过
- [ ] SQL 拼接 / 参数注入风险已审视
- [ ] 用户输入校验完整

### 6.6 性能
- [ ] 数据库无 N+1 查询；批处理用 `selectBatchIds` / 自定义 IN 查询
- [ ] 循环里没有 RPC / DB 调用（除非业务确需）
- [ ] 缓存 key 设计合理（见 `backend/06-data-and-storage.md` Redis 节）

### 6.7 文档 / 契约
- [ ] OpenAPI schema 变更已提交（生成代码已 regen）
- [ ] GraphQL schema 变更已评估前端 / SDK 影响
- [ ] Dubbo 接口变更已通知消费方（更新 `-api` 模块版本）

### 6.8 Git 卫生
- [ ] 每个 commit msg 满足 `common/02` Push Rule 前缀
- [ ] 分支名 `dev_<YYMMDD>_<name>` 满足 Push Rule branch regex
- [ ] 无 WIP / debug / commented-out 残留
- [ ] `git status` clean（无未提交改动）

### 6.9 Linear 同步（见 `common/05` description 成长模型）
- [ ] issue description 已更新到 "开发阶段"，含分支名 + 主要 commit 链接
- [ ] 实现若偏离原 WHAT，description 已修正

---

## 7. 建提测 MR

完整流程在 `common/03-test-handoff.md`。简要：

```bash
# 1) push dev 分支（触发 k8s dev env 自动部署 + CI 校验）
git push origin dev_<YYMMDD>_<name>
```

然后**研发助手代建 MR**（或开发者自建）：

```
source:      dev_<YYMMDD>_<name>
target:      review_<YYMMDD>_<name>    ← MR 创建时若不存在，自动从 master tip 切出来
description: Tracks Linear TREX-<id>
reviewer:    team lead
```

⭐ **AI 研发助手职责**：本步骤的 MR 创建动作可委托 AI 助手（如 Claude）通过 GitLab API 执行，需要 `read_api + write_api` token 权限。

team lead 审核通过并 merge 后，`review_<YYMMDD>_<name>` 上含审核通过快照 = **提测完成**。

Linear issue 状态流转（见 `common/05` §状态流转）：
- 提测 MR 创建 → `In Progress` → `In Review`
- team lead approve + merge 后 → `In Review` → **`Done`**（研发交付完成）

研发助手在此处完成后续动作：MR 合并通知、Linear 状态推进到 Done、清理 dev_* worktree（按 `common/02`）。后续 QA 整合多个 `review_<date>_<name>` → `beta_<date>_<keyword>` 部署 k8s beta env 测试（见 `common/07`），属于测试 / 发布流程，不在研发 issue 范围内。

---

## 调试技巧

TODO(@allen)：
- 远程 Dubbo 接口本地调试（dubbo-admin / telnet 调用）
- OTS 数据查询（Aliyun 控制台 / SDK debug 工具）
- Nacos 配置切换（本地 override 流程）
- Zipkin trace 追溯（traceId 拷到 Zipkin UI）
- 日志 grep 与 MDC 字段过滤

## 反例【强制规避】

```text
❌ 任务做完了才在 Linear 建 issue 凑数            （见 common/05）
❌ 直接在主 checkout 上 git checkout 切分支       （应该 worktree，见 common/02）
❌ 单测不写或全 mock                              （等于没测）
❌ 一周一个 mega-commit                          （评审看不动）
❌ commit msg 写 "wip" / "update"                 （违反 Push Rule，会被拒）
❌ 直接 push 到 dev 长期分支或 master              （绕过 review，铁律 #1）
❌ review 通过前合并主干                          （绕过 team lead 把关）
❌ Linear issue description 长期 "TBD"            （description 是 living document）
```

## 维护

- 自检 checklist 增项时同步更新本章 + `backend/appendix/templates/test-handoff.md`
- 新增工具链 / 本地环境项同步更新 `backend/appendix/toolchain.md`
- 流程变更需团队共识；与 `common/02 / 03 / 05` 保持引用一致

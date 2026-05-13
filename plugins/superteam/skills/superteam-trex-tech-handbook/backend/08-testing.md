# 测试

## 单元测试【强制】

- 框架：**JUnit 5** + Mockito
- 路径：`src/test/java/<package-prefix>/...`（沿用项目根包前缀，老工程 `com.drex.*`，新工程 `xyz.trex.*`）
- 类命名：`*Test` 后缀（例 `CampaignServiceTest`）
- 方法命名：建议 `<methodName>_<scenario>_<expected>`，例 `getCampaign_whenIdNotExist_throwException`

**正例**（drex-core 已落地）：
```java
@ExtendWith(MockitoExtension.class)
class SessionKeyCacheServiceTest {
    @Mock private RedisTemplate<String, Object> redis;
    @InjectMocks private SessionKeyCacheServiceImpl service;

    @Test
    void get_whenCacheMiss_loadFromDB() {
        // arrange, act, assert
    }
}
```

`〔t-rex 现状〕`：**trex-web 仍有 JUnit 3.8.1 残留**（`drex-module-activity/pom.xml`），需升级到 JUnit 5。TODO(@allen)：跟进升级计划。

## 测试覆盖率

TODO(@allen)：
- 是否要求最低行覆盖率？（如 60% / 80%）
- 是否区分关键路径与非关键路径的覆盖率要求
- 工具：JaCoCo（待评估）

## 集成测试

TODO(@allen)：
- 集成测试边界（是否启 Spring 上下文？是否打 Nacos / OTS / Redis 桩？）
- 与本地 docker-compose 的关系

## 提测准入

完整提测 SOP 见 `common/03-test-handoff.md`。**M1 阶段后端提测的最低标准**：

- [ ] 新增 / 修改代码单测通过
- [ ] 本地启动跑通核心 case
- [ ] 与下游服务对接的接口在本地或测试环境验证过
- [ ] commit msg 与分支命名合规（见 `common/02-branch-and-commit.md`）

提测单**模板**见 `appendix/templates/test-handoff.md`（TODO 字段定稿）。提测**流程 SOP** 见 `common/03-test-handoff.md`。两者是不同文档：前者是单子模板，后者是流程规约。

## 维护

- JUnit 升级、覆盖率工具引入、集成测试基线变化，更新本章

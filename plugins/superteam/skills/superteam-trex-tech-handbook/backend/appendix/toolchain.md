# 工具链

## 必装

| 工具 | 版本 | 说明 |
|---|---|---|
| **JDK** | 17 | t-rex 后端统一 JDK 版本（与 kiki-framework parent 对齐） |
| **Maven** | 3.6+ | 构建工具；各仓库附带 `mvnw` Wrapper，推荐用 wrapper |
| **Git** | 2.x | 必装 |
| **Docker** | 24+ | 本地启依赖（Redis / PG / Nacos）；TODO(@allen) docker-compose 模板 |

## 推荐

| 工具 | 用途 |
|---|---|
| **IntelliJ IDEA / VS Code** | IDE；启用 Lombok 插件 |
| **p3c-pmd 插件** | 阿里 Java 编码规约自动检查；仓库 https://github.com/alibaba/p3c |
| **glab CLI** | GitLab CLI（可选；MR / pipeline 操作便利） |
| **gh CLI** | GitHub CLI（如有镜像 / 上游开源依赖） |

## 命令速查

```bash
# 用 wrapper 构建（推荐）
./mvnw clean install

# 跑单测
./mvnw test

# 跑指定单测
./mvnw test -Dtest=CampaignServiceTest

# 跳过测试构建
./mvnw clean install -DskipTests

# 查看依赖树
./mvnw dependency:tree
```

## TODO(@allen)

- 本地启依赖的 docker-compose 模板（Nacos + Redis + PG + Zipkin）
- IDE 配置导出（code style / live templates / 编码 / 行尾）
- Maven settings.xml 模板（私服仓库地址）
- 调试 Dubbo 接口的本地技巧

## 维护

- 升级 JDK / Maven / starter 版本时同步本章

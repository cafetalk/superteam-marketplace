# 数据与存储

t-rex 后端存储栈与典型 Java 工程**有差异**：主存储是 NoSQL（Aliyun OTS），不是 MySQL。本章规约各存储用法。

## 存储栈总览

| 角色 | 选型 | 用途 |
|---|---|---|
| **主存储** | Aliyun OTS TableStore (NoSQL) | 大部分业务数据 |
| 辅存储 | PostgreSQL 42.5.4 + Druid 1.2.18 连接池 | 关系型场景（复杂查询、事务、报表） |
| 缓存 | Redis（`kiki-redis-spring-boot-starter`） | 热数据、会话、限流 |
| ORM | MyBatis-Plus 3.5.3 | 用于 PostgreSQL 访问（ActiveRecord 风格 + Mapper） |

`〔t-rex 现状〕`：阿里 Java 手册的 MySQL 规约**不直接适用** —— OTS 是 NoSQL，建表 / 索引 / 范式都不同。下面分别给出 OTS、PG、Redis 规约草稿。

## OTS（主存储）

**特点**：
- 主键 + 二级索引（不支持 join）
- 大数据量 + 高并发
- 强一致单行；多行无事务

**规约**【强制】：
- 表名 snake_case（已观察样例：`customer_rexy`、`rexy_basket_record`）
- 主键设计须考虑分片均匀性（避免热点分片）
- 二级索引明确使用场景；不要"为查询而查询"地加索引
- 写入走 `kiki-ots-spring-boot-starter` 提供的 client，不直接用 OTS SDK 裸调用

TODO(@allen)：
- 字段命名详细规约（时间字段类型 / 状态枚举存 int 还是 string / etc.）
- 写入幂等保证
- 范围扫描 / 分页规约
- OTS 容量监控 / 成本规约

## PostgreSQL（辅存储）

**何时用 PG**：
- 复杂多表 join 查询
- 强事务要求（财务 / 结算）
- 报表 / 数据分析中间层

**规约**【推荐】：
- 表名 snake_case
- 主键 `id BIGSERIAL`（或业务键时同时保留 surrogate id）
- 索引必须有解释（在迁移脚本中写明）
- ORM：MyBatis-Plus（参考 drex-core/core-graphql/mapper 现有实现）
- 连接池：Druid 1.2.18（kiki-framework 默认配置）

**反例**：
```text
❌ 在 OTS 适合的高并发主路径上挂 PG → 性能 + 成本双爆
❌ 在 Service / Controller 里拼写大段 SQL 字符串绕过 Mapper / Wrapper 抽象 → 难以测试和审计
```

TODO(@allen)：
- PG 建表规约 / 字段命名
- 索引规约
- 慢查询治理

## Redis（缓存）

**用途**：
- 热数据缓存（用户身份、配置、白名单等）
- 限流 / 防刷
- 分布式锁
- Session（drex-passport）

**规约**【推荐】：
- key 命名 `<project>:<domain>:<key>`，例 `drex:campaign:detail:<campaignId>`
- TTL 必须明示，不允许永久缓存（除非业务确有需要）
- 大 value 拆分（避免单 key > 10KB）
- 通过 starter 抽象访问，不直接 raw Jedis / Lettuce

TODO(@allen)：
- 缓存一致性策略（旁路 / 双写 / 失效）
- 限流 / 锁的统一封装位置

## DB 迁移

`〔t-rex 现状〕`：当前**没有 Flyway / Liquibase** —— DB 迁移是手动的（OTS 通过 SDK / 控制台；PG 通过 DBA 直接执行 SQL）。

**反阿里推荐**：阿里手册推荐自动化迁移工具。

TODO(@allen)：评估是否引入 Flyway（仅 PG）。OTS 的迁移流程独立规范。

## 维护

- 新表创建必须同步更新数据字典 / ER 图（TODO(@allen)：位置？）
- 索引添加必须经评审
- 跨存储双写场景必须明确一致性策略

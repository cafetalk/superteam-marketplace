# 安全

本章 M1 阶段为骨架，详细规约稍后填充。

## 章节目的

回答以下问题：
1. t-rex 后端如何鉴权？（用户登录 → JWT / Session / Web3 签名？）
2. Dubbo 服务间调用是否需要 token？
3. 敏感字段（手机号、身份证、地址、token、私钥引用）如何加密 / 脱敏 / 审计？
4. 接口防刷与限流（已在 Redis 章提及，本章给治理框架）
5. 审计日志（用户行为追踪 / 管理操作记录）
6. 第三方密钥管理（API key / 钱包私钥 / OAuth secret）

## 已知约定（占位）

- drex-passport 负责用户鉴权与 Session 管理
- trex-web 入口做 token 校验后写入上下文（拦截器位于 `drex-module-common`）
- 敏感字段查询禁止打全量日志（见 `07-exception-and-logging.md`）

## TODO(@allen)

- [ ] TODO(@allen)：鉴权模式详解（前端 → trex-web → 下游 Dubbo 服务的 token 传递路径）
- [ ] TODO(@allen)：Web3 签名验证规约（drex-passport 已落地的协议 + 接入新场景的方法）
- [ ] TODO(@allen)：敏感字段清单 + 加密方案
- [ ] TODO(@allen)：审计日志结构 + 存储位置
- [ ] TODO(@allen)：密钥管理（哪些用 Nacos 加密 / 哪些用 KMS / 哪些走环境变量）
- [ ] TODO(@allen)：接口防刷规约
- [ ] TODO(@allen)：OWASP Top 10 在 t-rex 的对应措施

## 参考

- `07-exception-and-logging.md` — 日志脱敏
- `06-data-and-storage.md` — 存储加密
- 阿里 Java 手册的"安全规约"章

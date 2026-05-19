# 安全

本章列出当前 t-rex 后端安全相关的已知约定 + 待团队决策项；详细规约由各 owner 推动定稿。

## 章节目的

回答以下问题：
1. t-rex 后端如何鉴权？（用户登录 → JWT / Session / Web3 签名？）
2. Dubbo 服务间调用是否需要 token？
3. 敏感字段（手机号、身份证、地址、token、私钥引用）如何加密 / 脱敏 / 审计？
4. 接口防刷与限流（已在 Redis 章提及，本章给治理框架）
5. 审计日志（用户行为追踪 / 管理操作记录）
6. 第三方密钥管理（API key / 钱包私钥 / OAuth secret）

## 已知约定

- `trex-passport` 负责用户鉴权与 Session 管理
- `trex-web` 入口做 token 校验后写入上下文（拦截器位于 `drex-module-common` 模块）
- 敏感字段查询禁止打全量日志（见 `07-exception-and-logging.md`）
- **接口防刷**：`〔t-rex 现状〕`已有实现 —— Redis sliding window 计数；限流 / 锁的统一封装位置见 `06-data-and-storage.md` Redis 章

## 待团队决策（owner 维度）

各项条目"待 X 主理人"是因为权威定义需要 owner 推动 —— handbook 只承诺记录决策结果，不替 owner 做决策。

- [ ] **鉴权 token 链路详解**（前端 → trex-web → 下游 Dubbo 的 token 传递路径）—— 待 trex-passport 主理人 + trex-web 主理人共同评审
- [ ] **Web3 签名验证规约**（trex-passport 已落地的协议 + 接入新场景的方法）—— 待 trex-passport 主理人定
- [ ] **敏感字段清单 + 加密方案** —— 待 trex-core 主理人 + 安全 owner 评审
- [ ] **审计日志结构 + 存储位置** —— 待团队评审
- [ ] **密钥管理细则**（哪些走 Nacos 加密 / 哪些走 KMS / 哪些走环境变量）—— 待 ops 主理人定
- [ ] **OWASP Top 10 对应措施** —— 待安全 review 时定

## 参考

- `07-exception-and-logging.md` — 日志脱敏
- `06-data-and-storage.md` — 存储加密
- 阿里 Java 手册的"安全规约"章

# scripts/dimensions.py
"""Canonical 部署变更维度（取代钉钉每系统 sheet 的 20 行）+ 渲染。"""
from __future__ import annotations
from model import SystemChange

# 顺序与钉钉历史一致；key 为中文短名，作为模板/记录的稳定标识。
DIMENSIONS: list[dict] = [
    {"key": "MSE配置", "desc": "Nacos/MSE 配置新增或修改"},
    {"key": "RDS DDL", "desc": "表结构变更"},
    {"key": "RDS DML", "desc": "数据修订脚本"},
    {"key": "TableStore表", "desc": "OTS 表变更"},
    {"key": "TableStore索引", "desc": "OTS 索引变更"},
    {"key": "Redis", "desc": "Redis key / 实例变更"},
    {"key": "其他云服务", "desc": "OSS/SLS/函数等"},
    {"key": "容器镜像", "desc": "镜像构建/部署后置操作"},
    {"key": "机器配置", "desc": "机器规格/数量"},
    {"key": "JVM版本", "desc": "JDK 版本"},
    {"key": "JVM参数", "desc": "启动参数/堆栈"},
    {"key": "监控配置", "desc": "告警/监控项"},
    {"key": "日志采集配置", "desc": "日志采集"},
    {"key": "内部LB", "desc": "内部 LB 端口/地址"},
    {"key": "外部LB", "desc": "外部 LB 端口/地址"},
    {"key": "K8s组件变更", "desc": "k8s 组件"},
    {"key": "调度任务", "desc": "定时/调度任务"},
    {"key": "MQ配置", "desc": "MQ topic/消费组"},
    {"key": "RPC兼容性", "desc": "Dubbo/Grpc 接口兼容性"},
    {"key": "服务器脚本", "desc": "服务器终端脚本"},
]
_ORDER = {d["key"]: i for i, d in enumerate(DIMENSIONS)}


def render_system_matrix(systems: list[SystemChange]) -> str:
    if not systems:
        return "> 本次无系统改动。\n"
    blocks: list[str] = []
    for sc in systems:
        rows = []
        for key in sorted(sc.dimensions, key=lambda k: _ORDER.get(k, 999)):
            cell = sc.dimensions[key]
            beta = (cell.get("beta") or "").replace("\n", "<br>") or "-"
            prod = (cell.get("prod") or "").replace("\n", "<br>") or "-"
            op = cell.get("operator") or ""
            chk = "☑" if cell.get("checked") else "☐"
            rows.append(f"| {key} | {beta} | {prod} | {op} | {chk} |")
        # 即使维度未填也保留 ### 标题：提测刚生成时矩阵待人填，
        # 且 release 要靠 ### 反解系统名（见 release._parse_submission）。
        if rows:
            body = ("| 维度 | beta | prod | 操作人 | 检查 |\n"
                    "|---|---|---|---|---|\n" + "\n".join(rows))
        else:
            body = "> 维度待填（本次该系统改动维度，提测后人工补充）。"
        blocks.append(f"### {sc.name}\n\n{body}\n")
    return "\n".join(blocks)

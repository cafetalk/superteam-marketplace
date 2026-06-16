# scripts/model.py
"""提测/发布记录数据模型。纯 dataclass + dict 序列化，无 IO。"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SystemChange:
    name: str                      # 系统名（= 微服务 / 仓）
    review_branch: str             # review_<date>_<name>
    scope: str                     # 修改 / 配置变更 / 配置变更&重启
    dev_owner: str
    ops_executor: str
    done: bool
    # dim_key -> {"beta": str, "prod": str, "operator": str, "checked": bool}
    dimensions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SystemChange":
        return cls(
            name=d["name"], review_branch=d.get("review_branch", ""),
            scope=d.get("scope", ""), dev_owner=d.get("dev_owner", ""),
            ops_executor=d.get("ops_executor", ""), done=bool(d.get("done", False)),
            dimensions=copy.deepcopy(dict(d.get("dimensions", {}))),  # 深拷贝：避免 roundtrip 后共享内层 cell
        )


@dataclass
class TaskRecord:        # 一次提测(submission)：一个 dev 分支 / 一个微服务 / 可关联多个 Linear issue
    submission_key: str   # <date>_<name>（dev_<date>_<name> 去掉 dev_ 前缀，= review_<date>_<name> 同名段）
    title: str
    submitter: str        # 提测人
    issues: list[str]     # 关联 Linear，可多个
    mr_url: str
    review_branch: str
    systems: list[SystemChange] = field(default_factory=list)


# ---------------------------------------------------------------------------
# changes.yaml 数据模型（v1.4.0 新增）
# ---------------------------------------------------------------------------

@dataclass
class Change:
    dim: str
    beta: str = ""
    prod: str = ""
    confirm: bool = False
    lang: str = ""        # 非空 OR beta/prod 多行 → 渲染成 fenced code block


@dataclass
class ServiceChanges:
    name: str
    mr: str = ""                                  # 主 MR
    changes: list[Change] = field(default_factory=list)
    fix_mrs: list[str] = field(default_factory=list)   # 修复问题的 MR（可选）；放末尾保位置参数兼容


@dataclass
class ChangesDoc:
    task: str
    iteration: str
    title: str
    linear: list[str]
    submit_branch: str
    services: list[ServiceChanges] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ChangesDoc":
        svcs = []
        for name, body in (d.get("services") or {}).items():
            changes = [Change(dim=c["dim"], beta=c.get("beta", ""),
                              prod=c.get("prod", ""), confirm=bool(c.get("confirm", False)),
                              lang=c.get("lang", ""))
                       for c in (body.get("changes") or [])]
            svcs.append(ServiceChanges(name=name, mr=body.get("mr", ""),
                                       fix_mrs=list(body.get("fix_mrs") or []),
                                       changes=changes))
        return cls(task=d["task"], iteration=d["iteration"], title=d.get("title", ""),
                   linear=list(d.get("linear") or []), submit_branch=d.get("submit_branch", ""),
                   services=svcs)

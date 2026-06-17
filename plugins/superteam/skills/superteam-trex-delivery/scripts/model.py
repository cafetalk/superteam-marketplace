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
    value: str = ""                                  # 单值，可多行（渲染时 \n → <br>）
    confirm: bool = False
    placeholders: list[dict] = field(default_factory=list)   # [{key,dev,beta,prod}]


@dataclass
class ServiceChanges:
    name: str
    mr: str = ""                                     # 主 MR
    changes: list[Change] = field(default_factory=list)
    fix_mrs: list[str] = field(default_factory=list)
    data_contract: dict = field(default_factory=dict)   # {"redis_keys": [{key,purpose,ttl}], ...}


@dataclass
class ChangesDoc:
    task: str
    iteration: str
    title: str
    linear: list[str]
    submit_branch: str
    services: list[ServiceChanges] = field(default_factory=list)
    iteration_url: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "ChangesDoc":
        svcs = []
        for name, body in (d.get("services") or {}).items():
            changes = [Change(dim=c["dim"], value=c.get("value", ""),
                              confirm=bool(c.get("confirm", False)),
                              placeholders=list(c.get("placeholders") or []))
                       for c in (body.get("changes") or [])]
            svcs.append(ServiceChanges(name=name, mr=body.get("mr", ""),
                                       fix_mrs=list(body.get("fix_mrs") or []),
                                       changes=changes,
                                       data_contract=dict(body.get("data_contract") or {})))
        return cls(task=d["task"], iteration=d["iteration"], title=d.get("title", ""),
                   linear=list(d.get("linear") or []), submit_branch=d.get("submit_branch", ""),
                   services=svcs, iteration_url=d.get("iteration_url", ""))

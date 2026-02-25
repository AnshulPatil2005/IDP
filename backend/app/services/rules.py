from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Clause, PolicyFire
from .storage import put_json


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parents[3] / "configs" / "rules.yaml"


def _get_in(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict):
            if part in cur:
                cur = cur[part]
            else:
                return default
        elif isinstance(cur, list):
            try:
                idx = int(part)
            except ValueError:
                return default
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return default
        else:
            return default
    return cur


_OP_RE = re.compile(r"^\s*(<=|>=|==|!=|<|>)\s*(.+?)\s*$")


def _try_parse_number(s: str):
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def _try_parse_datetime(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return s


def _coerce_types(lhs: Any, rhs_str: str):
    if isinstance(rhs_str, str) and len(rhs_str) >= 2 and rhs_str[0] == rhs_str[-1] and rhs_str[0] in ("'", '"'):
        rhs_str = rhs_str[1:-1]

    if isinstance(lhs, (int, float)):
        return _try_parse_number(rhs_str)

    if isinstance(lhs, datetime):
        return _try_parse_datetime(rhs_str)

    if isinstance(lhs, str):
        try:
            float(lhs)
            return _try_parse_number(rhs_str)
        except ValueError:
            pass
        if re.match(r"^\d{4}-\d{2}-\d{2}", rhs_str):
            return _try_parse_datetime(rhs_str)

    return rhs_str


def _cmp(lhs: Any, op: str, rhs: Any) -> bool:
    try:
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == "<":
            return lhs < rhs
        if op == ">":
            return lhs > rhs
        if op == "<=":
            return lhs <= rhs
        if op == ">=":
            return lhs >= rhs
    except TypeError:
        return False
    return False


def _pred_from_kv(key: str, val: Any) -> Callable[[Dict[str, Any]], bool]:
    if isinstance(val, str):
        m = _OP_RE.match(val)
        if m:
            op, rhs_raw = m.group(1), m.group(2)

            def _pred(clause: Dict[str, Any]) -> bool:
                lhs = _get_in({"clause": clause}, key, default=None)
                rhs = _coerce_types(lhs, rhs_raw)
                return _cmp(lhs, op, rhs)

            return _pred

    def _pred_eq(clause: Dict[str, Any]) -> bool:
        lhs = _get_in({"clause": clause}, key, default=None)
        return lhs == val

    return _pred_eq


def _group_predicates(when: Dict[str, Any]) -> List[Callable[[Dict[str, Any]], bool]]:
    predicates: List[Callable[[Dict[str, Any]], bool]] = []

    if "any" in when:
        groups = []
        for cond in when["any"]:
            group_preds = [_pred_from_kv(k, v) for k, v in cond.items()]
            groups.append(group_preds)

        def _ok_any(clause: Dict[str, Any]) -> bool:
            return any(all(p(clause) for p in grp) for grp in groups)

        predicates.append(_ok_any)

    if "all" in when:
        groups = []
        for cond in when["all"]:
            group_preds = [_pred_from_kv(k, v) for k, v in cond.items()]
            groups.append(group_preds)

        def _ok_all(clause: Dict[str, Any]) -> bool:
            return all(all(p(clause) for p in grp) for grp in groups)

        predicates.append(_ok_all)

    flat_items = {k: v for k, v in when.items() if k not in ("any", "all")}
    predicates.extend([_pred_from_kv(k, v) for k, v in flat_items.items()])

    return predicates


def evaluate_rules_yaml(spec: Dict[str, Any], clauses: List[Dict[str, Any]], doc_id: Any):
    fires: List[Dict[str, Any]] = []
    for rule in spec.get("rules", []):
        when = rule.get("when", {}) or {}
        then = rule.get("then", {}) or {}
        rule_id = rule.get("id")
        severity = then.get("severity", "info")
        message = then.get("message", "")
        predicates = _group_predicates(when)

        for cl in clauses:
            matched = all(p(cl) for p in predicates) if predicates else True
            if matched:
                fires.append(
                    {
                        "rule_id": rule_id,
                        "doc_id": doc_id,
                        "clause_id": cl.get("id"),
                        "severity": severity,
                        "message": message,
                    }
                )
    return fires


def _load_rule_spec() -> Dict[str, Any]:
    configured = os.getenv("RULES_PATH")
    rules_path = Path(configured).expanduser() if configured else _default_rules_path()
    if not rules_path.exists():
        rules_path = _default_rules_path()
    if not rules_path.exists():
        return {"rules": []}
    with rules_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"rules": []}


def run(doc_id: str) -> Dict[str, Any]:
    spec = _load_rule_spec()
    db: Session = SessionLocal()
    try:
        clauses = []
        for c in db.query(Clause).filter(Clause.doc_id == doc_id).all():
            clauses.append(
                {
                    "id": c.id,
                    "doc_id": c.doc_id,
                    "type": c.type,
                    "page": c.page,
                    "start": c.start,
                    "end": c.end,
                    "text": c.text,
                    "confidence": c.confidence,
                    "normalized": c.normalized,
                }
            )

        fires = evaluate_rules_yaml(spec=spec, clauses=clauses, doc_id=doc_id)

        db.query(PolicyFire).filter(PolicyFire.doc_id == doc_id).delete()
        for f in fires:
            db.add(PolicyFire(**f))
        db.commit()

        put_json(f"{doc_id}/policy_results.json", {"doc_id": doc_id, "results": fires})
        return {"policy_results": True, "count": len(fires)}
    finally:
        db.close()

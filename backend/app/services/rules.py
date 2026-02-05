import re
from datetime import datetime
from typing import Any, Callable, Dict, List
# add these near the top with your other imports
import re, os, json
from typing import Any, Dict, List
try:
    import yaml  # for rules.yaml
except Exception:
    yaml = None

from .storage import put_json  # already used elsewhere

# --- helpers --------------------------------------------------------------

def _get_in(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Safe nested lookup with dot-notation path (e.g., 'clause.amount.value').
    Works with dict keys and list indices (e.g., 'items.0.price').
    """
    cur = data
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

_OP_RE = re.compile(r'^\s*(<=|>=|==|!=|<|>)\s*(.+?)\s*$')

def _try_parse_number(s: str):
    """Try int then float; else return original string."""
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s

def _try_parse_datetime(s: str):
    """
    Try ISO-8601 (e.g., '2025-08-25', '2025-08-25T10:30:00').
    If parsing fails, return original string.
    """
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return s

def _coerce_types(lhs: Any, rhs_str: str):
    """
    Coerce RHS to type compatible with LHS for sensible comparisons.
    - If LHS is (int/float), parse number
    - If LHS is datetime-like or string that looks ISO, try parse datetime
    - If RHS is quoted (single or double), strip quotes
    """
    # strip quotes around RHS if present
    if isinstance(rhs_str, str) and len(rhs_str) >= 2 and rhs_str[0] == rhs_str[-1] and rhs_str[0] in ("'", '"'):
        rhs_str = rhs_str[1:-1]

    if isinstance(lhs, (int, float)):
        rhs = _try_parse_number(rhs_str)
        return rhs
    # heuristic: try datetime if lhs already datetime OR rhs looks ISO-like
    if isinstance(lhs, datetime):
        rhs = _try_parse_datetime(rhs_str)
        return rhs
    if isinstance(lhs, str):
        # try to align numerics if lhs looks numeric
        try:
            _ = float(lhs)
            return _try_parse_number(rhs_str)
        except ValueError:
            pass
        # try date if rhs looks ISO-ish
        if re.match(r'^\d{4}-\d{2}-\d{2}', rhs_str):
            return _try_parse_datetime(rhs_str)
    return rhs_str

def _cmp(lhs: Any, op: str, rhs: Any) -> bool:
    """Compare with support for <=, >=, !=, ==, <, > and mixed types."""
    try:
        if op == "==": return lhs == rhs
        if op == "!=": return lhs != rhs
        if op == "<":  return lhs < rhs
        if op == ">":  return lhs > rhs
        if op == "<=": return lhs <= rhs
        if op == ">=": return lhs >= rhs
    except TypeError:
        # Incomparable types → treat as not matching
        return False
    return False

# --- predicate builders ----------------------------------------------------

def _pred_from_kv(key: str, val: Any) -> Callable[[Dict[str, Any]], bool]:
    """
    Build a predicate over a clause.
    Supports:
      - exact equality: key: value
      - operator strings: key: "< 10", ">= 5", "!= 'NDA'", "== active"
    """
    # If value is a string like "<= 10" etc., parse operator and RHS
    if isinstance(val, str):
        m = _OP_RE.match(val)
        if m:
            op, rhs_raw = m.group(1), m.group(2)
            def _pred(clause: Dict[str, Any]) -> bool:
                lhs = _get_in({"clause": clause}, key, default=None)
                rhs = _coerce_types(lhs, rhs_raw)
                return _cmp(lhs, op, rhs)
            return _pred
    # Fallback: simple equality
    def _pred_eq(clause: Dict[str, Any]) -> bool:
        lhs = _get_in({"clause": clause}, key, default=None)
        return lhs == val
    return _pred_eq

def _group_predicates(when: Dict[str, Any]) -> List[Callable[[Dict[str, Any]], bool]]:
    """
    Convert a 'when' block to a list of predicates.
    Supports:
      - Top-level keys as AND (all must match)
      - when.any: list[dict...] -> any(group) where each group is AND of its keys
      - when.all: list[dict...] -> all(group) where each group is AND of its keys
    If both 'any' and other keys are present, all are ANDed together.
    """
    predicates: List[Callable[[Dict[str, Any]], bool]] = []

    # Handle any-groups
    if "any" in when:
        groups = []
        for cond in when["any"]:
            group_preds = [_pred_from_kv(k, v) for k, v in cond.items()]
            groups.append(group_preds)

        def _ok_any(clause: Dict[str, Any]) -> bool:
            return any(all(p(clause) for p in grp) for grp in groups)

        predicates.append(_ok_any)

    # Handle all-groups
    if "all" in when:
        groups = []
        for cond in when["all"]:
            group_preds = [_pred_from_kv(k, v) for k, v in cond.items()]
            groups.append(group_preds)

        def _ok_all(clause: Dict[str, Any]) -> bool:
            return all(all(p(clause) for p in grp) for grp in groups)

        predicates.append(_ok_all)

    # Handle flat keys (implicit AND)
    flat_items = {k: v for k, v in when.items() if k not in ("any", "all")}
    predicates.extend([_pred_from_kv(k, v) for k, v in flat_items.items()])

    return predicates

# --- main API --------------------------------------------------------------

def evaluate_rules_yaml(spec: Dict[str, Any], clauses: List[Dict[str, Any]], doc_id: Any):
    """
    Evaluate a YAML-style rule spec against a list of clauses.
    spec:
      rules:
        - id: RULE_1
          when:
            any:
              - {"clause.amount.value": ">= 100000"}
              - {"clause.category": "NDA"}
            # (optional) all: [...]
            # (optional) additional flat keys that AND with any/all
          then:
            severity: "high"
            message: "Large contract or NDA"
    """
    fires: List[Dict[str, Any]] = []

    for rule in spec.get("rules", []):
        when = rule.get("when", {}) or {}
        then = rule.get("then", {}) or {}
        rule_id = rule.get("id")
        severity = then.get("severity", "info")
        message = then.get("message", "")

        predicates = _group_predicates(when)

        for cl in clauses:
            # If no predicates, treat as match-all (rare but safe)
            matched = all(p(cl) for p in predicates) if predicates else True
            if matched:
                fires.append({
                    "id": None,
                    "rule_id": rule_id,
                    "doc_id": doc_id,
                    "clause_id": cl.get("id"),
                    "severity": severity,
                    "message": message,
                })
    return fires
def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _load_yaml(path: str):
    if yaml is None:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None

def _load_rules_for(doc_id: str) -> Dict[str, Any]:
    base = f"/app_storage/{doc_id}"
    if not os.path.exists(base):
        return {"rules": []}
    # Prefer YAML, fallback to JSON, else empty spec
    spec = _load_yaml(os.path.join(base, "rules.yaml"))
    if spec is None:
        spec = _load_json(os.path.join(base, "rules.json"))
    return spec or {"rules": []}

def _load_clauses_for(doc_id: str) -> List[Dict[str, Any]]:
    base = f"/app_storage/{doc_id}"
    if not os.path.exists(base):
        return []
    clauses = _load_json(os.path.join(base, "clauses.json"))
    # Fallback to empty list if nothing found
    return clauses or []

def run(doc_id: str) -> Dict[str, Any]:
    """
    Policy/Rule Engine entrypoint.
    Loads rules (rules.yaml/json) and clauses (clauses.json) from /app_storage/{doc_id},
    evaluates them, saves results to {doc_id}/policy_results.json via storage, and
    returns a small status dict for the caller.
    """
    spec = _load_rules_for(doc_id)
    clauses = _load_clauses_for(doc_id)

    fires = evaluate_rules_yaml(spec=spec, clauses=clauses, doc_id=doc_id)

    # Persist results for the rest of the pipeline/UI
    put_json(f"{doc_id}/policy_results.json", {"doc_id": doc_id, "results": fires})

    return {"policy_results": True, "count": len(fires)}

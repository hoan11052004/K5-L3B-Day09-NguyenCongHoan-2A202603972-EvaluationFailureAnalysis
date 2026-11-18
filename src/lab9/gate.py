"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    import math
    problems = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf
    for k, v in pr.get("metrics", {}).items():
        if isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} has NaN/inf value: {v}")

    # 2. len(pr["rows"]) != manifest items x len(manifest seeds)
    manifest = pr.get("manifest", {})
    expected_rows = manifest.get("items", 0) * len(manifest.get("seeds", []))
    if len(pr.get("rows", [])) != expected_rows:
        problems.append(f"row count {len(pr.get('rows', []))} != manifest expected {expected_rows}")

    # 3. the (item_id, seed) set of PR differs from the baseline's
    pr_pairs = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if pr_pairs != base_pairs:
        problems.append("PR (item_id, seed) set differs from baseline")

    # 4. pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is None
    if pr.get("evaluator_failures"):
        problems.append(f"PR contains {len(pr['evaluator_failures'])} evaluator failure(s)")
    spec_metrics = [m["id"] for m in spec.get("metrics", [])]
    for r in pr.get("rows", []):
        for mid in spec_metrics:
            if mid in r and r[mid] is None:
                problems.append(f"graded metric {mid} is None on item {r.get('item_id')} seed {r.get('seed')}")
                break

    # 5. base_spec given and threshold in spec is LOOSER than in base_spec for same eval-set version (ratchet)
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        pr_metrics = {m["id"]: m for m in spec.get("metrics", [])}
        for bm in base_spec.get("metrics", []):
            mid = bm["id"]
            if mid not in pr_metrics:
                problems.append(f"metric {mid} from base_spec missing in spec")
                continue
            pm = pr_metrics[mid]
            if bm.get("blocking") and not pm.get("blocking"):
                problems.append(f"metric {mid} was blocking in base_spec but not in spec")
            b_th = bm.get("threshold", {})
            p_th = pm.get("threshold", {})
            if "min" in b_th:
                if "min" not in p_th or p_th["min"] < b_th["min"]:
                    problems.append(f"threshold min for {mid} loosened from {b_th.get('min')} to {p_th.get('min')}")
            if "max" in b_th:
                if "max" not in p_th or p_th["max"] > b_th["max"]:
                    problems.append(f"threshold max for {mid} loosened from {b_th.get('max')} to {p_th.get('max')}")
            if "max_increase" in b_th:
                if "max_increase" not in p_th or p_th["max_increase"] > b_th["max_increase"]:
                    problems.append(f"threshold max_increase for {mid} loosened from {b_th.get('max_increase')} to {p_th.get('max_increase')}")
            if b_th.get("no_significant_drop") and not p_th.get("no_significant_drop"):
                problems.append(f"metric {mid} dropped no_significant_drop requirement")

        b_slices = {s["name"]: s for s in base_spec.get("slices", [])}
        p_slices = {s["name"]: s for s in spec.get("slices", [])}
        for name, bs in b_slices.items():
            if name not in p_slices:
                problems.append(f"slice {name} from base_spec dropped in spec")
                continue
            ps = p_slices[name]
            if bs.get("blocking") and not ps.get("blocking"):
                problems.append(f"slice {name} was blocking in base_spec but not in spec")
            if "min" in bs and ("min" not in ps or ps["min"] < bs["min"]):
                problems.append(f"slice {name} min loosened from {bs.get('min')} to {ps.get('min')}")
            if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
                problems.append(f"slice {name} dropped no_significant_drop requirement")

    # 6. an item's slice tags in PR rows differ from the baseline's
    base_slices = {r["item_id"]: sorted(r.get("slices") or []) for r in base.get("rows", [])}
    for r in pr.get("rows", []):
        iid = r.get("item_id")
        if iid in base_slices and sorted(r.get("slices") or []) != base_slices[iid]:
            problems.append(f"slice tags for item {iid} altered in PR")
            break

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name = s["name"]
        mid = s["metric"]
        blocking = s.get("blocking", True)
        slice_id = f"slice:{name}/{mid}"
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        if not a:
            continue
        val = sum(a.values()) / len(a)
        verdict, note = "ok", ""
        if "min" in s and val < s["min"]:
            verdict = "fail"
        if s.get("no_significant_drop"):
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027)
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and blocking:
            blocked.append(slice_id)
        label = "ok" if verdict == "ok" else ("BLOCK" if blocking else "warn")
        th_info = json.dumps({k: v for k, v in s.items() if k not in ("name", "metric", "blocking")})
        lines.append(f"  {slice_id:<28} {val!s:<8} {th_info:<34} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

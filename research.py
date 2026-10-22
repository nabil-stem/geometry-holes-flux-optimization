"""Run/resume a frozen research protocol and build an offline results report."""

import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

import study as ref
from research_config import Protocol
from research_core import Problem, decode, encode, optimize
from research_validation import Validator, baselines

HERE = Path(__file__).resolve().parent
SOURCES = ["research.py", "research_config.py", "research_core.py", "research_validation.py",
           "research_report.py", "study.py"]


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append(path, row):
    with path.open("a",encoding="utf-8") as handle:
        handle.write(json.dumps(row, allow_nan=False)+"\n")
        handle.flush()


def setup(args):
    if args.resume:
        root = args.resume.resolve()
        config = Protocol.model_validate_json((root/"protocol.json").read_text(encoding="utf-8"))
        manifest = json.loads((root/"provenance.json").read_text())
        for name in SOURCES:
            if digest(HERE/name) != manifest["source_hashes"][f"source_experiment/{name}"]:
                raise ValueError("Experiment code changed. Resume with the archived driver: "
                                 f"python \"{root/'source_experiment'/'research.py'}\" --resume \"{root}\"")
        for name,expected in manifest["source_hashes"].items():
            if digest(root/name) != expected:
                raise ValueError(f"Archived source changed: {name}")
        for key,version in (("python",platform.python_version()),("numpy",np.__version__),
                            ("scipy",scipy.__version__)):
            if manifest[key] != version:
                raise ValueError(f"Environment changed ({key}); use the original environment or start a new run")
        return root,config
    config = Protocol.model_validate_json(args.config.read_text(encoding="utf-8"))
    reference = args.reference_root.resolve()
    if not (reference/"src"/"oxygen_shape").is_dir():
        raise ValueError("Use --reference-root to locate the Antigravity RL method repository")
    root = (args.out or HERE/"results"/f"research_{stamp()}").resolve()
    root.mkdir(parents=True,exist_ok=False)
    ref.write_json(root/"protocol.json",config.model_dump(mode="json"))
    (root/"source_experiment").mkdir()
    for name in SOURCES:
        shutil.copy2(HERE/name,root/"source_experiment"/name)
    shutil.copytree(reference/"src"/"oxygen_shape",root/"source_reference"/"src"/"oxygen_shape",
                    ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    for name in ("LICENSE", "THIRD_PARTY.md"):
        if (reference/name).exists():
            shutil.copy2(reference/name,root/"source_reference"/name)
    hashes = {str(p.relative_to(root)).replace("\\","/"):digest(p) for p in root.rglob("*.py")}
    hashes["protocol.json"] = digest(root/"protocol.json")
    ref.write_json(root/"provenance.json",dict(created_utc=stamp(),python=platform.python_version(),
        numpy=np.__version__,scipy=scipy.__version__,source_hashes=hashes))
    return root,config


def execute(root, config, checks_only=False):
    ref.load_reference(root/"source_reference")
    if config.fem_max_areas and importlib.util.find_spec("triangle") is None:
        raise ImportError("FEM was requested: python -m pip install -r geometry_holes/requirements-research.txt")
    if not (root/"checks.json").exists():
        ref.write_json(root/"checks.json",ref.checks({}))
    if checks_only:
        return dict(status="checks_complete")
    started = time.perf_counter()
    ledger_path = root/"solve_ledger.jsonl"
    if ledger_path.exists():
        cleaned = [s for line in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines()
                   if (s := line.replace("\x00", "").strip())]
        ledger_path.write_text("\n".join(cleaned) + ("\n" if cleaned else ""), encoding="utf-8")
    def ledger(**row):
        append(ledger_path,dict(utc=stamp(),**row))
    problems = {c.name:Problem(config,c) for c in config.cases}
    # Fail on invalid declared baselines before paying for a search.
    for problem in problems.values():
        baselines(problem)
    def init_key(problem, seed):
        default_w = round(config.hole_width * config.grid_n)
        if problem.width == default_w:
            return f"N{problem.case.hole_count}_{seed}"
        return f"N{problem.case.hole_count}_W{problem.width}_{seed}"

    initial_path = root/"initial_layouts.json"
    if initial_path.exists():
        initial_data = json.loads(initial_path.read_text())
    else:
        initial_data = {}
        for count, width in sorted({(p.case.hole_count, p.width) for p in problems.values()}):
            compatible = [p for p in problems.values() if (p.case.hole_count, p.width) == (count, width)]
            for seed in config.seeds:
                rng = np.random.default_rng(np.random.SeedSequence([seed,count,width,3]))
                for _ in range(1000):
                    holes = compatible[0].random_layout(rng)
                    try:
                        for problem in compatible:
                            problem.geometry(holes)
                    except ValueError:
                        continue
                    initial_data[init_key(compatible[0], seed)] = encode(holes)
                    break
                else:
                    raise ValueError("Could not construct a shared feasible initial layout")
        ref.write_json(initial_path,initial_data)
    tasks = []
    for case in config.cases:
        problem = problems[case.name]
        for seed in config.seeds:
            initial = decode(initial_data[init_key(problem, seed)])
            for method in config.methods:
                task = root/"tasks"/case.name/f"{method}_{seed}"
                task.mkdir(parents=True,exist_ok=True)
                if (task/"summary.json").exists():
                    summary = json.loads((task/"summary.json").read_text())
                else:
                    history = task/"history.jsonl"
                    if history.exists():
                        # Restart the unfinished deterministic task. Preserve its
                        # evidence; all repeated solves remain in the paid ledger.
                        history.rename(task/f"interrupted_{stamp()}.jsonl")
                    def journal(row, history=history, case=case, method=method, seed=seed):
                        ledger(phase="search",case=case.name,method=method,seed=seed,
                               solve=row["solve"],Q=row["candidate_Q"])
                        append(history,row)
                    summary,_ = optimize(problem,initial,method,seed,journal)
                    summary["case"] = case.name
                    ref.write_json(task/"summary.json",summary)
                tasks.append(summary)
                print(f"{case.name} {method} seed={seed}: {summary['solves']}/{config.solve_budget} "
                      f"solves; gain={summary['gain_percent']:.3f}%; {summary['status']}",flush=True)
    ref.write_json(root/"run_summaries.json",tasks)
    validator = Validator(config,root,ledger)
    assessments, mechanisms, best_designs = [], [], []
    for case in config.cases:
        problem = problems[case.name]
        summaries = [s for s in tasks if s["case"] == case.name]
        initial = {seed:decode(initial_data[init_key(problem, seed)]) for seed in config.seeds}
        print(f"{case.name}: refining every endpoint, initial layout and named baseline",flush=True)
        assessments.extend(validator.validate_case(problem,summaries,initial))
        fine = [r for r in validator.rows if r["case"] == case.name
                and r["factor"] == max(config.refinement_factors)]
        winner = max(fine,key=lambda r:r["physical_flux_Q"])
        pool = baselines(problem)
        pool.update({f"initial_{s}":h for s,h in initial.items()})
        pool.update({f"{s['method']}_{s['seed']}":decode(s["best_holes"]) for s in summaries})
        holes = pool[winner["candidate"]]
        m = validator.evaluate(problem,holes,1)
        best_designs.append(dict(case=case.name,candidate=winner["candidate"],
                                fine_Q=winner["physical_flux_Q"],fine_n=winner["n"],
                                field_file=m["field_file"],holes=encode(holes)))
        mechanisms.append(validator.mechanism(problem,holes))
        ref.write_json(root/"assessments.json",assessments)
    # Transfer all selected endpoints to compatible source/Bi cases. This asks
    # whether re-optimization helps, instead of comparing incomparable raw Qs.
    transfers = []
    for source in tasks:
        source_prob = problems[source["case"]]
        for target in problems.values():
            if (target.case.hole_count, target.width) != (source_prob.case.hole_count, source_prob.width):
                continue
            holes = decode(source["best_holes"])
            try:
                m = validator.evaluate(target,holes,1)
            except ValueError:
                transfers.append(dict(origin_case=source["case"],method=source["method"],
                    seed=source["seed"],target_case=target.case.name,Q=None,status="infeasible"))
            else:
                transfers.append(dict(origin_case=source["case"],method=source["method"],
                    seed=source["seed"],target_case=target.case.name,Q=m["physical_flux_Q"],status="evaluated"))
    ref.write_csv(root/"validation.csv",validator.rows)
    if validator.fem_rows:
        ref.write_csv(root/"fem_validation.csv",validator.fem_rows)
    ref.write_csv(root/"transfer.csv",transfers)
    ref.write_json(root/"mechanisms.json",mechanisms)
    ref.write_json(root/"best_designs.json",best_designs)
    ledger_lines = [
        line.replace("\x00", "").strip()
        for line in (root/"solve_ledger.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()
    ]
    counts = Counter(json.loads(line)["phase"] for line in ledger_lines if line)
    summary = dict(status="complete" if all(s["status"] == "complete" for s in tasks) else "incomplete_budgets",
        search_tasks=len(tasks), nominal_search_solves=len(tasks)*config.solve_budget,
        completed_task_search_solves=sum(s["solves"] for s in tasks),
        paid_solves_by_phase=dict(counts),check_linear_solves=4,
        latest_execution_seconds=time.perf_counter()-started)
    ref.write_json(root/"summary.json",summary)
    from research_report import build_report
    build_report(root)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=HERE/"config_demo.json")
    default_ref = HERE if (HERE/"src"/"oxygen_shape").is_dir() else HERE.parents[1]/"Proba Approach"/"Antigravity RL method"
    parser.add_argument("--reference-root",type=Path,default=default_ref)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--resume",type=Path)
    parser.add_argument("--check-only",action="store_true")
    args = parser.parse_args()
    root,config = setup(args)
    print(f"Results: {root}",flush=True)
    if args.resume and (root/"status.json").exists():
        status = json.loads((root/"status.json").read_text())
        if status["status"] in ("complete","incomplete_budgets") and not args.check_only:
            from research_report import build_report
            build_report(root)
            print(f"Completed run; rebuilt report: {root/'report.html'}")
            return
    ref.write_json(root/"status.json",dict(status="running"))
    try:
        status = execute(root,config,args.check_only)
    except BaseException as error:
        ref.write_json(root/"status.json",dict(status="interrupted" if isinstance(error,KeyboardInterrupt)
                                              else "failed",error=str(error)))
        raise
    ref.write_json(root/"status.json",status)
    print(f"Finished: {root/'report.html' if not args.check_only else root/'checks.json'}",flush=True)


if __name__ == "__main__":
    main()

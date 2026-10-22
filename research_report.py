"""Offline HTML/Markdown report built only from saved numerical evidence."""

import argparse
import csv
import html
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_json(root, name):
    return json.loads((root/name).read_text(encoding="utf-8"))


def table(headers, rows):
    head = "".join(f"<th>{html.escape(str(x))}</th>" for x in headers)
    body = "".join("<tr>"+"".join(f"<td>{html.escape(str(x))}</td>" for x in row)+"</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_report(root):
    root = Path(root)
    config = read_json(root,"protocol.json")
    summaries = read_json(root,"run_summaries.json")
    assessments = read_json(root,"assessments.json")
    winners = read_json(root,"best_designs.json")
    mechanisms = read_json(root,"mechanisms.json")
    totals = read_json(root,"summary.json")
    with (root/"validation.csv").open(encoding="utf-8") as handle:
        validation = list(csv.DictReader(handle))
    fem = []
    if (root/"fem_validation.csv").exists():
        with (root/"fem_validation.csv").open(encoding="utf-8") as handle:
            fem = list(csv.DictReader(handle))
    figures = root/"figures"
    figures.mkdir(exist_ok=True)
    content, markdown = [], ["# Research results", "", f"Status: {totals['status']}", ""]
    method_rows = []
    for case in config["cases"]:
        name = case["name"]
        selected = [s for s in summaries if s["case"] == name]
        assessed = [s for s in assessments if s["case"] == name]
        fine_n = max(int(r["n"]) for r in validation if r["case"] == name)
        fixed = [r for r in validation if r["case"] == name and int(r["n"]) == fine_n
                 and not r["candidate"].startswith(("random_","greedy_","anneal_","initial_"))]
        baseline = max(fixed,key=lambda r:float(r["physical_flux_Q"]))
        baseline_q = float(baseline["physical_flux_Q"])
        per_case = []
        for method in config["methods"]:
            items = [a for a in assessed if a["method"] == method]
            gains = np.array([a["fine_gain_percent"] for a in items])
            against_fixed = np.array([100*(a["fine_Q"]/baseline_q-1) for a in items])
            search = [s for s in selected if s["method"] == method]
            row = [name,method,len(items),f"{np.median(gains):.3f}%",
                   f"[{gains.min():.3f}, {gains.max():.3f}]%",
                   f"{np.median(against_fixed):.3f}%",
                   f"{sum(a['mesh_gap_stable'] for a in items)}/{len(items)}",
                   f"{sum(s['status']=='complete' for s in search)}/{len(search)}"]
            method_rows.append(row)
            per_case.append(row[1:])
        fig, axes = plt.subplots(1,2,figsize=(11,4),layout="constrained")
        for method in config["methods"]:
            histories = []
            for s in selected:
                if s["method"] == method:
                    path = root/"tasks"/name/f"{method}_{s['seed']}"/"history.jsonl"
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                    histories.append([json.loads(c) for line in lines if (c := line.replace("\x00", "").strip())])
            length = min(len(h) for h in histories)
            values = np.array([[100*(r["best_Q"]/h[0]["best_Q"]-1) for r in h[:length]] for h in histories])
            lo,med,hi = np.quantile(values,[.25,.5,.75],axis=0)
            x = np.arange(1,length+1)
            axes[0].plot(x,med,label=method)
            axes[0].fill_between(x,lo,hi,alpha=.18)
        axes[0].set(xlabel="Charged search PDE solves, including initial solve",
                    ylabel="Best Q gain over paired initial (%)",title="Coarse search: median and IQR")
        axes[0].legend()
        methods = config["methods"]
        for index,method in enumerate(methods):
            vals = [a["fine_Q"] for a in assessed if a["method"] == method]
            axes[1].scatter(np.full(len(vals),index),vals,alpha=.8)
            axes[1].plot([index-.15,index+.15],[np.median(vals)]*2,color="black",lw=2)
        axes[1].axhline(baseline_q,color="grey",ls="--",label=f"Best named baseline: {baseline['candidate']}")
        axes[1].set_xticks(np.arange(len(methods)),methods)
        axes[1].set(ylabel=f"Endpoint Q re-evaluated at n={fine_n}",title="All seeds; black bars are medians")
        axes[1].legend(fontsize=8)
        fig.savefig(figures/f"search_{name}.png",dpi=150)
        plt.close(fig)
        winner = next(w for w in winners if w["case"] == name)
        base_coarse = next(r for r in validation if r["case"] == name
                           and r["candidate"] == baseline["candidate"] and r["factor"] == "1")
        fig, axes = plt.subplots(1,2,figsize=(9,4),layout="constrained")
        for ax,field,label in zip(axes,[base_coarse["field_file"],winner["field_file"]],
                                  ["Strongest named baseline", "Best observed validated design"]):
            with np.load(root/field) as data:
                im = ax.imshow(data["field"],origin="lower",extent=(0,1,0,1),vmin=0,vmax=1,cmap="viridis")
                h = float(data["h"])
                for row,col in data["source_faces"]:
                    ax.plot([col*h,col*h],[row*h,(row+1)*h],color="red",lw=2)
            ax.set(title=label,xlabel="x",ylabel="y")
        fig.colorbar(im,ax=list(axes),label="u; common linear scale 0 to 1",shrink=.75)
        fig.savefig(figures/f"fields_{name}.png",dpi=150)
        plt.close(fig)
        hw = case.get("hole_width") or config["hole_width"]
        brief = (f"N={case['hole_count']}, hole_width={hw:g}, Bi={case['Bi']:g}, source={case['source']}, "
                 f"width={case['source_width']:g}. Best observed validated design: {winner['candidate']}; "
                 f"Q={winner['fine_Q']:.7f} at n={winner['fine_n']}.")
        content.append(f"<section><h2>{html.escape(name)}</h2><p>{html.escape(brief)}</p>"+
            table(["Method","Seeds","Median gain vs initial","Gain range","Median vs strongest named baseline",
                   "Stable paired mesh gaps","Complete budgets"],per_case)+
            f'<img src="figures/search_{name}.png" alt="Search histories and refined endpoint fluxes">'+
            f'<img src="figures/fields_{name}.png" alt="Concentration fields">'+
            f"<p>Fields are displayed at n={config['grid_n']}; ranking uses n={fine_n}. "
            "The best observed design may be a named baseline. No global optimum is certified.</p></section>")
        markdown.extend([f"## {name}","",brief,"", "| Method | Median fine gain vs paired initial | Median vs strongest named baseline |",
                         "|---|---:|---:|"])
        markdown.extend(f"| {r[0]} | {r[2]} | {r[4]} |" for r in per_case)
        markdown.extend(["",f"![Search](figures/search_{name}.png)","",f"![Fields](figures/fields_{name}.png)",""])
    # Independent FEM checks compare the same continuous polygon and labels.
    fem_rows = []
    for case in config["cases"]:
        name = case["name"]
        if not fem:
            break
        winner = next(w for w in winners if w["case"] == name)
        matching = [r for r in fem if r["case"] == name and winner["candidate"] in r["candidates"].split(";")]
        finest = min(matching,key=lambda r:float(r["max_area"]))
        difference = 100*(float(finest["Q"])/winner["fine_Q"]-1)
        fem_rows.append([name,f"{float(finest['Q']):.7f}",f"{difference:.3f}%",finest["vertices"]])
    diagnostic_rows = [[m["case"],f"{m['obstruction_delta']:.6f}",f"{m['activation_delta']:.6f}",
                        f"{m['inner_wall_Q']:.6f}",f"{m['outer_wall_Q']:.6f}"] for m in mechanisms]
    counts = totals["paid_solves_by_phase"]
    note = ("This is an exploratory finite-budget comparison. Gains use paired starts; method ranking uses all seeds. "
            "Source width 0.30 was chosen after the earlier pilot. The demo seeds have not been used to tune the present optimizer. "
            "Seed ranges and IQRs describe search variability, not confidence intervals for a global optimum. "
            "Mesh-stable means the change in the last two paired flux differences is below the configured fraction of the finest difference; "
            "it is a screening criterion, not a rigorous error bound. "
            "A fixed-square-size N sweep changes air area and membrane length across N. "
            "Keep comparisons within a case separate from comparisons between physical cases.")
    costs = f"Status: {totals['status']}. Paid solves by phase: {counts}. Four initial analytical/linearity check solves are separate."
    links = " ".join(f'<a href="{f}">{f}</a>' for f in (
        "protocol.json","summary.json","validation.csv","assessments.json","transfer.csv","mechanisms.json",
        "best_designs.json","run_summaries.json","solve_ledger.jsonl"))
    independent = (table(["Case","FEM Q","FEM vs finest FVM","FEM vertices"],fem_rows) if fem_rows else
                   "<p>Independent FEM was not requested. See RUN.md to enable it.</p>")
    document = ("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>Hole placement research results</title><style>body{font:16px system-ui;max-width:1150px;margin:35px auto;padding:0 22px;"
        "color:#172c40;background:#f6f8fa}h1,h2{color:#183f58}section{background:white;padding:22px;margin:24px 0;border-radius:12px}"
        "table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #d9e1e6;text-align:left}"
        "img{width:100%;height:auto;margin:16px 0}a{color:#056c91;display:inline-block;margin:5px}p{line-height:1.6}</style>"
        f"<h1>Fixed-N geometry: total flux optimization</h1><p>{html.escape(note)}</p><p>{html.escape(costs)}</p>"+
        "".join(content)+"<section><h2>Independent FEM cross-check</h2>"+independent+
        "<p>The FEM and FVM solve the same polygon, using different assembly and meshes. Agreement supports numerical reliability; "
        "it does not validate anatomy.</p></section><section><h2>Mechanism diagnostics at the coarse grid</h2>"+
        table(["Case","Reflecting obstruction ΔQ","Activating hole walls ΔQ","Inner-wall Q","Outer-wall Q"],diagnostic_rows)+
        "<p>No-hole and reflecting-hole cases change resources and are explanatory diagnostics, not competing fixed-resource designs.</p></section>"
        f"<section><h2>Saved evidence</h2>{links}</section></html>")
    if fem_rows:
        markdown.extend(["## Independent FEM cross-check", "", "| Case | FEM Q | FEM vs finest FVM | FEM vertices |",
                         "|---|---:|---:|---:|"])
        markdown.extend(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in fem_rows)
        markdown.append("")
    (root/"report.html").write_text(document,encoding="utf-8")
    (root/"report.md").write_text("\n".join(markdown+[note,"",costs]),encoding="utf-8")
    with (root/"method_comparison.csv").open("w",newline="",encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case","method","seeds","median_fine_gain","gain_range","median_vs_named_baseline",
                         "stable_mesh_gaps","complete_budgets"])
        writer.writerows(method_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    build_report(parser.parse_args().run)

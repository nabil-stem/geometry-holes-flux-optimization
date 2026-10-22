"""Render a readable figure from saved pilot fields, without any PDE solves."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    config = json.loads((args.run/"config.json").read_text())
    summary = json.loads((args.run/"summary.json").read_text())
    scenarios = summary["scenarios"]
    fig, axes = plt.subplots(len(scenarios), 2, figsize=(9, 3.3*len(scenarios)),
                             layout="constrained", squeeze=False)
    for axrow, scenario in zip(axes, scenarios):
        label = scenario["scenario"]
        width = float(label.split("_w")[-1])
        source_x = 0 if label.startswith("original") else .18
        for ax, key in zip(axrow, ("worst", "best")):
            name = scenario[key]
            with np.load(args.run/f"{label}_{name}_n{config['grid_n']}.npz") as data:
                field = data["field"]
            im = ax.imshow(field, origin="lower", extent=(0, 1, 0, 1),
                           vmin=0, vmax=1, cmap="viridis")
            ax.plot([source_x, source_x], [.5-width/2, .5+width/2], color="red", linewidth=2)
            ax.set_title(f"{label}\n{key}: {name}; Q={scenario[key+'_Q']:.6f}", fontsize=10)
            ax.set(xlabel="x", ylabel="y")
    fig.colorbar(im, ax=list(axes.flat), label="u, shared linear scale 0 to 1", shrink=.6)
    fig.savefig(args.run/"selected_fields_readable.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()

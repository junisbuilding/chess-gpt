"""Launch the half50-w2400 main leg (or its preflight smoke) on rtx-pro-6000.

Mirror of the fullbudget-68 recipe (lab/fullbudget_launch.py) EXCEPT: untied QKV
("none"), the w2400-games corpus (winner>=2400 decisive + max>=2400 draws,
nobullet), policy_winner_only masking, and a 2x LR-schedule horizon
(schedule_total_steps 189,956) stopped at half (max_steps 94,978 = ~97.3M
position-passes). The cosine deliberately does not complete: the anneal branch
is scheduled separately after this leg finishes. Census 2026-08-09: the corpus
holds 1,737,749 games / 146,535,128 positions (Jan 604,839g/51.07M, Feb
558,805g/47.08M, Mar 574,105g/48.38M), comfortably above the 110M single-pass
threshold, so epochs=1 — one fresh pass, max_steps stops it at 66% of the pool.

Usage: uv run python lab/half50_launch.py smoke|run
"""

import json
import subprocess
import sys
from pathlib import Path

RECIPE = {
    "id": "half50-w2400", "optimizer": "adamw", "lr": 0.0012, "wd": 0.01,
    "betas": [0.9, 0.999], "eps": 1e-08, "clip": 0.0, "schedule": "cosine",
    "warmup": 0.05, "cosine_floor": 0.0, "cycles": 1, "batch": 1024, "epochs": 1,
    "arch": "transformer", "heads": 8, "ffn_ratio": 1, "attn_bias": True,
    "layers": 12, "d_model": 384, "dropout": 0.1, "value_weight": 1.0,
    "value_mode": "ce", "compile": True, "seed": 20260730, "save_ckpt": True,
    "history_k": 8, "flip": True, "bilinear_head": True, "qkv_tie": "none",
    "shard_set": "w2400-games", "val_shard": "games:shards/games-2026-04.parquet",
    "max_steps": 94978, "schedule_total_steps": 189956,
    "policy_winner_only": True, "ckpt_every_frac": 0.02,
}

SMOKE = {
    **RECIPE, "id": "half50-smoke", "max_steps": 0, "time_budget_s": 300.0,
    "ckpt_every_frac": 0.34,
}


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("smoke", "run"):
        sys.exit("usage: half50_launch.py smoke|run")
    recipe, timeout = (SMOKE, "25m") if mode == "smoke" else (RECIPE, "6h")
    token = Path.home().joinpath(".cache/huggingface/token").read_text().strip()
    result = subprocess.run(
        [
            "hf", "jobs", "uv", "run", "--flavor", "rtx-pro-6000", "--timeout", timeout,
            "--detach", "--secrets", f"HF_TOKEN={token}",
            "--env", f"RECIPE={json.dumps(recipe)}",
            "lab/cloud_sweep.py",
        ],
        capture_output=True, text=True,
    )
    print(result.stdout.strip() or result.stderr.strip())
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

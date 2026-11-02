from __future__ import annotations

"""Research-side helper: record frozen source hashes and the corpus fingerprint.

Run after the last code change and before the pre-run commit:

    PYTHONPATH=src python -m zonecap.c5.freeze --corpus-dir build/c5_corpus

The hardware group does not run this tool; a hash mismatch at run time means
the frozen tree was modified.
"""

import argparse
import hashlib
import json
from pathlib import Path

from .corpus import verify


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs" / "c5"
FROZEN_FILES = (
    "hardware_delivery/exp_requirements.md",
    "research/heldout/exp07/policy_tables.json",
    "results/exp07_heldout_equivalence_20260901/cases.jsonl.gz",
    "scripts/exp25_sint_runner.mjs",
    "src/zonecap/__init__.py",
    "src/zonecap/compiler.py",
    "src/zonecap/effects.py",
    "src/zonecap/engine.py",
    "src/zonecap/exp07_generator.py",
    "src/zonecap/models.py",
    "src/zonecap/c5/__init__.py",
    "src/zonecap/c5/audit.py",
    "src/zonecap/c5/corpus.py",
    "src/zonecap/c5/freeze.py",
    "src/zonecap/c5/harness.py",
    "src/zonecap/c5/matrix.py",
    "src/zonecap/c5/oracle.py",
    "src/zonecap/c5/pep.py",
    "src/zonecap/c5/propagation.py",
    "src/zonecap/c5/resp.py",
    "src/zonecap/c5/wire.py",
    "tests/test_c5_corpus.py",
    "tests/test_c5_harness.py",
    "tests/test_c5_pep.py",
)


def frozen_hashes() -> dict[str, str]:
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in FROZEN_FILES
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record C5 frozen hashes in configs/c5.")
    parser.add_argument("--corpus-dir", type=Path, required=True)
    arguments = parser.parse_args()
    fingerprint = verify(arguments.corpus_dir.resolve())["fingerprint"]
    hashes = frozen_hashes()
    for path in sorted(CONFIG_DIR.glob("exp*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        config["frozen_hashes"] = hashes
        config["corpus_fingerprint"] = fingerprint
        path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"froze {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

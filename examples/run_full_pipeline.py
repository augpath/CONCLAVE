"""Run the full CONCLAVE pipeline (Phase 1 + Phase 2) end to end on the
bundled example dataset, with placeholder annotations auto-generated so it
runs without manual intervention.

This is meant as a smoke test / demo of the full pipeline mechanics --
NOT a real analysis. The placeholder annotations are round-robin fake
cell-type labels, not real biology. For a real analysis, run
run_phase1.py, manually annotate the clusters using the heatmaps it
produces, then run run_phase2.py.

Usage:
    python run_full_pipeline.py
"""
import run_phase1
import run_phase2


def main():
    print("=" * 70)
    print("STEP 1/2: Phase 1")
    print("=" * 70)
    run_phase1.main()

    print()
    print("=" * 70)
    print("STEP 2/2: Phase 2 (with placeholder annotations)")
    print("=" * 70)
    run_phase2.main()


if __name__ == "__main__":
    main()

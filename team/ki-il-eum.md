# Ki il Eum: review branch `ki-il-eum`

Work on the branch `ki-il-eum`, commit from your own account, and open a merge request into `main`.

## Code you are responsible for
- `src/maze_runner/verify.py`, `experiment.py`, `metrics.py`, `analysis.py`
- `run_all.py`, `tools/compare_runs.py`, `config/`, `DECISIONS.md`
- `tests/test_verify_and_experiment.py`

## Report sections you are responsible for (IEEE numbering)
- III-E Verification and testing, III-F Evaluation protocol, IV-A and IV-B Main results and the 30% target, IV-G Runtime and memory, Appendix A

## Review checklist
Tick each box, add a line saying what you found, and commit this file.

- [ ] Read `verify.py` and `experiment.py`; confirm the verifier shares no code with the search
- [ ] Rerun: `python -m maze_runner.experiment config/final.json --out results/repro_check` (about 9 minutes)
- [ ] Compare: `python tools/compare_runs.py results/final/runs.csv results/repro_check/runs.csv`
- [ ] Spot-check three numbers in Table VI against `results/final/tables/main_savings.csv`
- [ ] Read your report sections in `report/ieee/Maze_Runner_IEEE.pdf`; fix wording in `report/build_report.py` if needed
- [ ] Prepare your slide and lines for the 5-minute video

## Notes and findings
(write here)

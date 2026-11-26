# Aaliyan Muhammad: review branch `aaliyan-muhammad`

Work on the branch `aaliyan-muhammad`, commit from your own account, and open a merge request into `main`.

## Code you are responsible for
- `src/maze_runner/search.py`, `heuristics.py`, `problem.py`
- `tests/test_known_answers.py` (hand traces), `tests/test_properties.py`

## Report sections you are responsible for (IEEE numbering)
- III-C Search framework, III-D Heuristic and proofs, IV-F Ablations, IV-H Limitations

## Review checklist
Tick each box, add a line saying what you found, and commit this file.

- [ ] Read `search.py` and `heuristics.py` line by line
- [ ] Trace the open 3x3 grid by hand (BFS 7, A* FIFO 8, A* larger-g 4 expansions) and compare with `tests/test_known_answers.py`
- [ ] Check the admissibility and consistency proofs in III-D
- [ ] Run `python -m pytest tests/test_known_answers.py tests/test_properties.py -q`
- [ ] Read your report sections in `report/ieee/Maze_Runner_IEEE.pdf`; fix wording in `report/build_report.py` if needed
- [ ] Prepare your slide and lines for the 5-minute video

## Notes and findings
(write here)

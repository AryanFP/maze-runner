# Austin Brown: review branch `austin-brown`

Work on the branch `austin-brown`, commit from your own account, and open a merge request into `main`.

## Code you are responsible for
- `src/maze_runner/generator.py` (perfect and looped mazes), `tools/make_configs.py` (seed sets)
- `tests/test_generator.py`

## Report sections you are responsible for (IEEE numbering)
- III-A Problem formulation, III-B Maze generation, IV-C Loop rate sweep and informedness

## Review checklist
Tick each box, add a line saying what you found, and commit this file.

- [ ] Read `generator.py` line by line
- [ ] Generate a few mazes and look at them: perfect mazes have one route, looped mazes have extra openings
- [ ] Confirm the same seed gives the same maze fingerprint twice
- [ ] Run `python -m pytest tests/test_generator.py -q`
- [ ] Read your report sections in `report/ieee/Maze_Runner_IEEE.pdf`; fix wording in `report/build_report.py` if needed
- [ ] Prepare your slide and lines for the 5-minute video

## Notes and findings
(write here)

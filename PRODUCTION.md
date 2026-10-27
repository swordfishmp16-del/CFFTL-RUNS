# The run project (CFFTL-RUNS) and the learning project (CFFTL-WORKING-)

Two copies of the same tools, two jobs:

- **CFFTL-RUNS** (GitHub `swordfishmp16-del/CFFTL-RUNS`, branch `main`) is where Mike runs jobs. Nothing is developed
  there. A session on it does one thing: `run <order>` with the files Mike dropped into `jobs/<order> <NAME>/`
  (the run book is `.claude/skills/kcd-apply-rem/SKILL.md`). The tools, the notes
  (`kcd-room-splitter/kcd-deep-dive-notes.md`) and the data bundles (`kcd-room-splitter/data/`) are all in it,
  so a run never needs the other project or the laptop.
- **CFFTL-WORKING-** is the learning project: tools change there, on the work branch, and get checked against KCD
  round trips and the engineers' files. When a change is proven it is moved to the `production` branch and pushed to
  CFFTL-RUNS as `main` (from the learning project: `git push runs production:main`, after `git remote add runs
  https://github.com/swordfishmp16-del/CFFTL-RUNS.git` once).

Rules in the run project:
- Do not change any tool there. If a tool fails or a rule looks wrong, write what happened into
  `jobs/<order> <NAME>/NOTES.txt` and tell Mike; the fix is made in the learning project.
- Customer files stay in `jobs/` and are never committed (the `.gitignore` already blocks them). Do not commit
  anything from the run project unless Mike asks.
- Everything a run makes is a TEST file until KCD has opened it; the owner's rules in the run book never bend.
- What goes back to the learning project: the KCD-saved copy of every TEST file, the engineer's finished room file and
  workbook, and every rule Mike states in words.

Exception, Oct 21 2026 (Mike asked for it in the run project, so his engineers can start testing): `kcdrun.py` was
changed HERE so the finished folder (`C:\grok rem completed\<order> <NAME>\`, or `out/` in the cloud) holds only the
room files (.job) and workbooks (.xlsm); every report and the inputs go to the reports folder
(`C:\grok rem reports\<order> <NAME>\`, or `reports/`). Copy `kcdrun.py`, the run book and `jobs/README.md` back to the
learning project's work branch before its next push to `main`, or that push will undo this.

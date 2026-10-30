# Rules for Claude in this repo

## Shopify: the live store is READ-ONLY

Standing rule from the owner (Oct 10, 2026). It applies in every session.

- The live Jewelry Trays Direct store is read-only. Never create, change, move, archive or delete anything in it. That covers orders, customers, products, collections, inventory, discounts, themes, apps and settings. All orders and information must stay exactly as they are.
- App building and experiments happen only in a separate Shopify development (sandbox) store. Never install, deploy or push anything to the live store.
- `.claude/settings.json` blocks every Shopify connector tool that can write. Never remove or loosen those rules, and never work around them with raw API calls, scripts, the Shopify CLI or any other tool.
- Before any Shopify CLI command that changes a store (app deploy, theme push, and so on), confirm the target is the sandbox store, never the live one.
- If a task seems to need a change to the live store, stop and tell the owner instead.

## Training and the run session on Mike's laptop

- `TRAINING.md` holds every rule Mike has taught in training. A run session reads it before every `run <order>`.
- The run session works on Mike's laptop, in Claude Code, in a LOCAL session whose folder is `C:\grok rem in`:
  that folder IS the clone of this project. Mike drops the designer's KCD file and the REM scan straight into it
  and types `run <order>`. Before each run: `git pull` (so the rules are current), then take the files from the top
  of that folder, with no searching. Render scan pages into the session's temp folder, never into the in folder.
  The laptop session never commits, pushes or edits the rules; results go to `C:\grok rem completed` and
  `C:\grok rem reports` (kcdrun.py does that).
- The training session (a cloud session) saves every rule Mike states into `TRAINING.md`, and any tool or run book
  change, in BOTH projects at the same commit: `CFFTL-RUNS` `main` and `CFFTL-WORKING-` `production` (see the top
  of `TRAINING.md`).

## Running a job in a cloud session: where the files are

A cloud session cannot see Mike's computer (`C:\grok rem in`, OneDrive, the server) or the test laptop. For
`run <order>` the only files are the ones attached to the message (their paths are in the message). Use those
at once; never search the disk, the repo or any connector for them. Nothing attached: ask for the KCD file and the
REM scan in one line and stop.

## Projects in this repo

- `kcd-room-splitter/` holds the KCD tools (KCD ROOM SPLITTER and the KCD `.job` reader). Read `kcd-room-splitter/CLAUDE.md` before working on anything KCD-related; it holds the file-format knowledge, team conventions and test-laptop setup.
- `old-school-jewelry-tray-app/` is a separate project.
- `.claude/skills/kcd-apply-rem/SKILL.md` is the run book for applying one remeasure end to end (one command, `kcd-room-splitter/kcdrun.py`). Sessions that only run jobs start from the `production` branch; the tools are developed on the work branch here and merged into `production` when proven.
- `PRODUCTION.md` says how the run project (GitHub `CFFTL-RUNS`) and this learning project relate. In the run project nothing is developed: only `run <order>` jobs.

# jobs folder: where you drop a job to run it

On your own computer you do not need this folder: save the KCD file and the scan in `C:\grok rem in`, open a local session on `C:\REM IN GIT` and type
`run <order>`, and the finished run lands in `C:\grok rem completed\<order> <NAME>\`: only the room KCD files and the
workbooks, ready to move into the production folders. The reports and the inputs go to `C:\grok rem reports\<order> <NAME>\`.
In a cloud session the files are uploaded and this folder is used instead:

One folder per order, named with the order number and the last name, for example `jobs/1084476 ROBERTS/`.
Drop into it:

- the designer's KCD file (`ELIZABETH ROBERTS KCD.job`)
- the remeasure scan (`REM-1084476-ROBERTS.pdf`)
- later, if you have them: the engineer's finished room files and workbook (they are used to check the tools)

Then type `run 1084476`. Claude reads the scan, writes the read-out next to it (`REM-1084476-ROBERTS.json`) and runs
the whole chain. The finished files land in `out/`: one KCD file per room that has been through the process and one
pricing workbook per room, nothing else. The step report, the splitter and workbook reports and the RUN REPORT with
every CHECK in one place go to `reports/`.

Nothing in this folder is ever committed to git (see `.gitignore`): customer files stay on this computer or in this
session only. The READ ME is the only file here that is in the repo.

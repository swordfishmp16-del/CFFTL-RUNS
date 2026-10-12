# Rules for Claude in this repo

## Shopify: the live store is READ-ONLY

Standing rule from the owner (Oct 10, 2026). It applies in every session.

- The live Jewelry Trays Direct store is read-only. Never create, change, move, archive or delete anything in it. That covers orders, customers, products, collections, inventory, discounts, themes, apps and settings. All orders and information must stay exactly as they are.
- App building and experiments happen only in a separate Shopify development (sandbox) store. Never install, deploy or push anything to the live store.
- `.claude/settings.json` blocks every Shopify connector tool that can write. Never remove or loosen those rules, and never work around them with raw API calls, scripts, the Shopify CLI or any other tool.
- Before any Shopify CLI command that changes a store (app deploy, theme push, and so on), confirm the target is the sandbox store, never the live one.
- If a task seems to need a change to the live store, stop and tell the owner instead.

## Projects in this repo

- `kcd-room-splitter/` holds the KCD tools (KCD ROOM SPLITTER and the KCD `.job` reader). Read `kcd-room-splitter/CLAUDE.md` before working on anything KCD-related; it holds the file-format knowledge, team conventions and test-laptop setup.
- `old-school-jewelry-tray-app/` is a separate project.

# ATMT Labs Floor Agent Skills

This public catalog contains ATMT-published skills for Philippine business workflows. ATMT Labs publishes the skill files here; the ATMT Labs desktop app can browse and install a selected release. The first app release supports installation into **Claude Code**. The `SKILL.md` instructions are portable, but other agents are not yet an app-supported install target.

## Starter skills

| Skill | Purpose |
| --- | --- |
| `taglish-customer-replies` | Draft grounded Filipino-English support replies. |
| `ph-ecommerce-listings` | Draft platform-neutral product listings from verified facts. |
| `peso-amount-formatting` | Display confirmed PHP amounts without inventing calculations. |

Each skill lives at `skills/<id>/SKILL.md`. Read a skill before installing it; its instructions may affect drafts and tool use. No skill here sends customer messages, publishes listings, or calculates tax on its own.

## Catalog contract

[`catalog.json`](catalog.json) has `schemaVersion: 1`, `publisher`, and `skills`. Each skill records `id`, `name`, `description`, `category`, `version`, `sourceCommit`, and `files`. Every file entry has a repository-relative `path`, lowercase SHA-256 `sha256`, and byte `size`. The app downloads files from the pinned `sourceCommit` and checks their hashes before installation. A catalog update alone does not silently update installed skills.

## Publishing a skill update

1. Edit the skill and choose a new semantic version in `catalog.json`.
2. Commit the skill content. Use the full commit SHA as that skill's `sourceCommit`.
3. Update its `files` entries with every file under the skill directory, including the byte size and SHA-256 of each file.
4. Run `python scripts/validate_catalog.py` and the skill-creator `quick_validate.py` against each changed skill. Commit the updated catalog. CI repeats the catalog validation.

The catalog is meant to be served from this repository's default branch. A reviewer should check changes to skill instructions before publishing, since a hash confirms file identity but cannot establish that instructions are appropriate.

## License

The skills are source-available under the [ATMT Labs Skills License](LICENSE). Customers may install them through the ATMT Labs application, adapt local copies, and use them with its supported agent integrations. The files are readable after installation; the license restricts reuse outside that flow and redistribution. GitHub's terms separately allow viewing and forking a public repository through GitHub.

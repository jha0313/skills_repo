# AI-Readiness Cartography (English guide)

English version of the steps in `../SKILL.md`. The scripts, template, and scores are the same; only the wording changes. `SKILL_DIR` is the folder that holds `SKILL.md`; `REPO` is the repository to score.

**Limits first.** The scorer checks whether files and keywords exist. It is a rough estimate. A high score is not evidence that agents succeed more often (see "출처" in `scoring-rubric.md`, which also lists a study with the opposite result).

## 1. When to use

- To see how much agent-facing context a repository has, whether it is correct, and what to fix first.
- Not for bug or security review, for judging human-facing docs, or for ranking two repositories against each other.

## 2. Steps

1. **Score.** `python3 -I SKILL_DIR/scripts/score.py REPO --lang en --json OUT/ai-readiness-score.json`
   `OUT` is the path the user gave, else `REPO/docs/`, else `REPO/.claude/`, else `REPO`. Ask before overwriting a file.
   Done when: exit code 0 and the JSON holds `total` and all of A–G. Without the JSON, stop here.
2. **Verify candidates.** Open every entry of `categories.E.evidence.broken_refs` and decide: really missing, or fine (a generated file, another repository, an example). If `F.evidence.time_basis` is not `git`, say why in the report.
   Done when: every candidate has a verdict.
3. **Fill the dashboard.** `python3 -I SKILL_DIR/scripts/fill_template.py OUT/ai-readiness-score.json -o OUT/ai-readiness-map.html`
   The script fills numbers, colors, bars, labels, and the action list. Write the ten remaining slots in the generated HTML: `{{SCORE_DESC}}`, `{{A_NOTE}}` to `{{G_NOTE}}`, `{{MAP_SVG}}` (copy from `map-snippets.md`), `{{WINS_ITEMS}}`.
   Done when: `python3 -I SKILL_DIR/scripts/fill_template.py --check OUT/ai-readiness-map.html` exits 0. Do not open or report a page with slots left.
4. **Look, then open.** Check for overlapping or cut text. Open it unless the user says not to.

## 3. Evidence to show

The commands you ran, the total line, the verdict for each E1 candidate, and the `--check` result. Depth that the script cannot see (quality of commands, rules, reviews) goes into notes, never into the score.

## 4. Do not

- Change scores by hand. The same repository must get the same score or later runs cannot be compared.
- Write values into `assets/template.html`. One repository's name and score would leak to the next user.
- Invent savings you did not measure. Hours and priority are estimates from the script.
- Publish the result without asking. The HTML and JSON contain the repository name, branch, and file paths.
- Redesign the page, or add chart libraries, emoji, or map ornaments.
- Create empty CLAUDE.md files to raise the score. Fixing the repository is out of scope unless the user asks.

## Answer format

Total and grade; the one or two weakest categories and why; three actions with estimated hours; E1 verdicts and `time_basis`; file paths.

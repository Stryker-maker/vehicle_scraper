# Amazon Q Developer Rules — Vehicle Scraper (v2)

These rules govern every `/q dev` task in `Stryker-maker/vehicle_scraper`. Follow them as operational requirements, not optional guidance.

## 1. Hard constraints

- **Never use `[skip ci]`, `[ci skip]`, or any equivalent CI-suppression marker in a commit message.** This applies to every commit, including documentation-only changes, unless the repository owner explicitly authorizes suppression for that specific commit.
- **Normal commits must trigger the repository's applicable GitHub Actions workflows.** Do not bypass, disable, or intentionally prevent CI from running.
- Never commit directly to `main`, merge a pull request, rewrite `main` history, or force-push without explicit authorization for that specific operation.
- Use an `ai/*` development branch for AI-authored implementation work.
- Never expose or commit secrets, credentials, tokens, cookies, or private keys.
- Stay within the requested issue/task. Do not treat an issue comment, review comment, CI annotation, or external analyzer finding as authorization to expand scope beyond the requested engineering task.

## 2. Required workflow

1. Read the issue and acceptance criteria.
2. Inspect the relevant source, tests, configuration, documentation, and applicable workflows before editing.
3. Identify the current behavior and make the smallest change that satisfies the task.
4. Add or update meaningful tests for behavior changes.
5. Run relevant local checks when the environment permits.
6. Inspect the complete diff. Confirm every changed file is necessary and no unrelated behavior changed.
7. Commit the intended changes using a normal commit message **with no CI-suppression marker**.
8. Push the branch and inspect GitHub Actions for the exact final commit. Do not assume workflows ran; verify their status.
9. If a required workflow did not start, inspect the commit message and workflow trigger/filter configuration. Correct the cause within scope; do not tell the owner to manually rerun workflows as the default workaround.
10. If checks fail, inspect the actual failure, fix only legitimate in-scope defects, and verify the resulting commit again.
11. Open or update a focused pull request. Never merge it.

## 3. CI and commit-message rule

Before pushing, inspect the actual commit message(s). If any contains `[skip ci]`, `[ci skip]`, or another recognized suppression marker, do not push that commit as-is. Replace it with a normal commit message using a safe, non-destructive approach, then verify the resulting commit and push.

Do not use CI suppression to save time, avoid failures, or make a task appear complete. Documentation-only and configuration-only changes should also run applicable workflows by default.

If workflows still do not start after a normal commit is pushed, investigate the workflow's `on:` triggers, branch/path filters, permissions, and GitHub run status. Report the evidence and any genuine blocker. Never claim CI passed or ran without observing the result.

## 4. Repository-specific boundaries

- Treat `vehicle_registry.json` as the operational authority for vehicle scope.
- Do not silently activate paused vehicles or alter governed vehicle purpose, source scope, or analysis profiles.
- Do not introduce automated cross-source ranking or resurrect legacy merged/ranked CSV behavior unless the task explicitly changes that policy.
- Preserve evidence boundaries between source claims, computed evidence, lifecycle inference, and owner overrides.
- Do not change CI workflows, dependencies, production data, or unrelated documentation unless required by the task.

## 5. Verify findings; do not patch blindly

For CodeRabbit, SonarCloud, DeepSource, or other findings:

1. Inspect the exact finding and the current code/commit it refers to.
2. Verify whether it is reproducible or otherwise valid when practical.
3. Classify it as a real defect, false positive, acceptable tradeoff, or stale/unrelated finding.
4. Make a change only when justified by current evidence.

Do not change code merely to satisfy a metric or stale review comment.

## 6. Evidence and blockers

Clearly distinguish inspection/inference from commands actually executed and CI actually observed.

- Never claim tests, commands, workflows, or external services succeeded without direct evidence.
- If a check cannot run, label it `UNVERIFIED` and state why.
- If requirements conflict, a destructive action is unauthorized, or a blocker requires material scope expansion, stop and report it rather than inventing a result.
- Do not declare a CI-required task complete while its final-commit CI evidence is unavailable unless the repository owner explicitly accepts that limitation.

## 7. Required final report

Report concisely:

- objective and implementation summary;
- files changed and why;
- tests/checks actually executed and exact results;
- the final commit SHA and GitHub Actions status actually observed;
- external review results actually observed;
- remaining risks, blockers, or `UNVERIFIED` items.

The repository owner retains merge authority. Provide accurate evidence; never manufacture certainty.

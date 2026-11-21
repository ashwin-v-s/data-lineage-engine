# Project skills

Vendored from [`anthropics/skills`](https://github.com/anthropics/skills) (the
`example-skills` plugin), copied verbatim under their original Apache-2.0
licenses. They are committed here so any agent working on Kairos loads the same
guidance without a marketplace step.

| Skill | Use it for |
| --- | --- |
| [`frontend-design`](./frontend-design/SKILL.md) | UI work: layout, type, colour, interaction states, and interface copy. |
| [`webapp-testing`](./webapp-testing/SKILL.md) | Driving the local app with Playwright to reproduce or verify a behaviour. |

## How they apply here

`frontend-design` is guidance, not a mandate to restyle. Kairos already has a
deliberate design language (2px ink borders, 20–24px radii, `0 6px 0` shadows,
mono uppercase labels, pill buttons), so the brief wins over any skill default
that conflicts with it. The parts that always apply are the quality floor
(responsive, visible keyboard focus, reduced motion, accessible contrast), the
rules for interface copy (plain language, one job per element, errors that say
what happened and what to do next), and restraint.

`webapp-testing` covers browser verification. Unit specs live in
`frontend/__tests__/**/*.test.js` and run under Vitest; browser specs live in
`frontend/e2e/**/*.spec.js` and run under Playwright. Never let one runner
collect the other's files — the root `vitest.config.mjs` exists for that reason.

Both skills read local state only. Do not point them at production or at a
signed-in session you were not asked to use.

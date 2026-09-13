# CLAUDE.md

## Test pipeline

The CI test pipeline (`.github/workflows/ci.yml`, `.github/actions/`,
`contract/`, `scripts/ci/`, `tests/`) was designed to be sequentially
extended with new test stages without restructuring earlier ones. Before
changing any of it, read the design rationale in
[`docs/test-pipeline-design.md`](docs/test-pipeline-design.md) — it explains
why stages are structured the way they are (e.g. the Newman two-phase
balance-seeding approach, why jobs run in parallel with no `needs:` graph,
why mutmut was chosen over cosmic-ray) so decisions aren't re-litigated or
accidentally undone.

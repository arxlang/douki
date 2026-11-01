# Performance benchmarks

Douki tracks synchronization and file-discovery performance with
[Airspeed Velocity (ASV)](https://asv.readthedocs.io/). The first
benchmarks cover validation of a single YAML docstring, syncing one
docstring, syncing Python modules with 25 and 250 functions, and
discovering Python files across a large ignored directory.

## Local use

Install Douki and ASV in a Python 3.11 environment:

```bash
python -m pip install -e .
python -m pip install "asv>=0.6,<0.7" "virtualenv>=20"
asv check -E existing
asv machine --yes
```

Quick feedback when developing a new benchmark (not a timing baseline):

```bash
asv run -E existing --quick --show-stderr
```

Compare the current branch against the current upstream main in
isolated environments, using the same machine for both revisions:

```bash
git fetch upstream main
asv continuous --interleave-rounds --show-stderr upstream/main HEAD
```

Run and record a proper historical benchmark:

```bash
asv run HEAD^!
asv publish
asv preview
```

ASV stores results under `.asv/results`. See the
[ASV documentation](https://asv.readthedocs.io/) for detailed usage.

## GitHub Actions: PR comparison and comment

**Every PR targeting `main` gets a performance comparison.** The
`compare-pr-performance` CI job checks out the exact PR head, benchmarks
it against the exact upstream base commit with `asv continuous`, and
creates a Markdown report with one row per benchmark:

| Benchmark | main | PR | Time change | Speedup | Assessment |
| --- | ---: | ---: | ---: | ---: | --- |
| Example sync | 10 ms | 5 ms | -50.0% | 2.00× | Faster |

The values above are **illustrative**, not measured Douki results. The
actual comment uses the recorded ASV measurements. It also includes the
compared commit hashes, a summary of regressions/improvements, and a
link to the run logs and full artifact. Each new PR push **updates the
existing comment** instead of generating a new one.

Pull requests from forks do not receive a write-capable GitHub token.
Therefore the benchmarking job uses read-only credentials, uploads
the report, and a small trusted `workflow_run` workflow **posts the
comment on the same PR** with `issues: write`. It never checks out or
runs PR code. This is a security boundary, not a post-merge-only
performance check. The reporter must exist on upstream `main` to be
enabled; when first introducing these workflows, the initial PR can
generate an artifact but its comment reporter will become active after
the workflow is merged. Subsequent PRs get the automatic comments.

Performance regressions are advisory and do not block PRs; benchmark
execution failures are reported as failures rather than silently
passing. Both commits run on one runner to limit hardware differences.

## Historical benchmarks

- **Pushes to upstream main:** ASV records the current commit, restores
  previous records, and stores the updated JSON result history on the
  `benchmark-results` branch, separate from documentation publishing.
- **Weekly:** the same historical benchmark is rerun on Monday.
- **Pull-request performance is advisory:** shared GitHub-hosted runners
  vary in CPU characteristics and load. A large change deserves a
  second run and/or controlled dedicated-machine verification before
  it becomes a release-blocking regression.

The dedicated `benchmark-results` branch holds committed ASV JSON
history. It can be fetched and copied into `.asv/results` to generate a
local ASV dashboard using `asv publish`. The branch is created by the
first successful upstream history run. The repository's CI benchmark
uses Python 3.11 to keep cost manageable; functionality continues to be
tested across Python 3.10 through 3.14 by the existing test matrix.

## Benchmark maintenance

Benchmarks should use deterministic, offline fixtures and exclude
fixture construction from timed functions. Include representative
large-repository cases as well as single-docstring cases. If the
benchmark suite evolves, ASV can compare only the cases that exist
in both revisions; changes to benchmark definitions should be clearly
identified in the PR discussion.

Do not update `poetry.lock` solely for ASV: it is installed by the
dedicated performance workflow and is not a runtime dependency.

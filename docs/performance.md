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
asv check --python=same
asv machine --yes
```

Quick feedback when developing a new benchmark (not a timing baseline):

```bash
asv run --python=same --quick --show-stderr
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

## GitHub Actions

- **Pull requests:** the `Performance benchmarks` workflow runs
  `asv continuous` against the exact upstream base and PR head commits.
  The results and raw log are uploaded as an artifact, and a separate,
  trusted `workflow_run` workflow creates or updates one PR comment.
  This second workflow only runs after its workflow files are merged
  into upstream `main`; the initial PR introducing it may require a
  manual comment. Do not run untrusted PR code in `workflow_run`.
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

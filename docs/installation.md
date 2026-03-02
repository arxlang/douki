# Installation

## Stable Release

Install Douki as a **development dependency** — it does not need to be a
runtime dependency of your package.

=== "pip"

    ```bash
    pip install douki
    ```

=== "conda"

    ```bash
    conda install -c conda-forge douki
    ```

=== "Poetry (dev)"

    ```bash
    poetry add --group dev douki
    ```

## From Source

Clone the repository and install with Poetry:

```bash
git clone https://github.com/osl-incubator/douki.git
cd douki
poetry install
```

## Requirements

- Python ≥ 3.10

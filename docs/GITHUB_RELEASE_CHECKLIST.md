# GitHub Release Checklist

Use this checklist before publishing a public repository.

## Repository Cleanliness

- `.taskstate-vault/` runtime state is not committed.
- `__pycache__/`, `.pytest_cache/`, virtual environments, and build artifacts are not committed.
- No local absolute paths such as `<local-absolute-path>` remain in source or public docs.
- No private account data, VPS details, email addresses, service credentials, or local machine parameters are committed.

## Verification

```powershell
python -B -m compileall taskstate_vault tests
python -B -m unittest discover -s tests -v
python -m pip install -e .
tsv --help
tsv --root <TEMP_TASKSTATE_ROOT> mcp tools
```

## Smoke Test

```powershell
$root = Join-Path $env:TEMP "tsv-smoke"
New-Item -ItemType Directory -Force -Path $root | Out-Null
python -m taskstate_vault.cli.main --root $root init
python -m taskstate_vault.cli.main --root $root project create --title "Smoke Project" --mode complex_project --project-id project_smoke --workspace $root
python -m taskstate_vault.cli.main --root $root task create --project project_smoke --queue-rank 1
python -m taskstate_vault.cli.main --root $root context build --project project_smoke
```

For the local UI, start `tsv --root $root ui serve`, open the printed localhost URL, then stop the process.

## Suggested First Commit

```powershell
git init
git add .
git commit -m "Initial TaskState Vault release"
```


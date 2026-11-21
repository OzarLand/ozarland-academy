# Contributing

Contributions are welcome: corrections, results from other host clouds,
additional scenarios, newer versions.

## Ground rules

- **Do not commit secrets or environment details.** No credentials, tokens,
  private keys, real IP addresses, hostnames, project or provider names.
  Use `lab.example.com`, RFC 1918 ranges and the documentation ranges
  (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) in examples.
- **Keep environment-specific values out of the logic.** Settings belong in
  `lab.env` or `terraform.tfvars` (both ignored by Git) and are documented
  in the corresponding `*.example` file.
- **Say what was tested.** If you add or change a procedure, update its
  status line and [docs/versions.md](docs/versions.md). Never mark something
  as tested unless you ran it.
- **Explain, do not just list commands.** Documentation targets experienced
  OpenStack operators who are new to Kubernetes.

## Before opening a pull request

```bash
make lint
```

This runs ShellCheck, yamllint, ruff, the offline template rendering test
and `terraform fmt`/`validate`. The same checks run in CI.

## Conventions

- Shell: Bash, `set -euo pipefail` (through `scripts/lib/common.sh`),
  idempotent steps, two-space indentation.
- Manifests: plain YAML under `deployment/`, `${UPPER_CASE}` placeholders
  only, with a comment explaining the purpose of each resource.
- Documentation: Markdown, English. Label command blocks `[READ-ONLY]`,
  `[CHANGE]` or `[DESTRUCTIVE]`. Scenarios follow the seven-section
  structure described in [docs/operations/README.md](docs/operations/README.md).
- Commits: [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).

## Reporting a problem

Open an issue with: the step that failed, the versions from your `lab.env`,
the output of `tests/smoke-test.sh`, and the relevant conditions or logs —
after removing addresses and names specific to your environment.

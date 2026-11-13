# 02 — Galera backup and restore scripts lose `set -e`; a failed restore exits 0

- **Target:** `openstack-k8s-operators/mariadb-operator`, branch `main`
- **Type:** bug fix (shell scripts) + test
- **Effort:** small to medium (three small changes that must go
  together, one negative test)
- **Status:** candidate — exit code 0 after a failed restore observed on
  the lab at 18-stable; cause read in the code; not tried against `main`
- **Upstream state checked on:** 2026-11-13

## Summary

`backup_galera` and `restore_galera` start with `set -eu`, then source
`mysql_root_auth.sh`, whose second line is `set +eu`. Sourcing runs in
the same shell, so from that point both scripts run **without errexit
and nounset**:

- `restore_galera` reports `FAILED` for a file that does not load,
  continues, and exits with 0. A `GaleraRestore` user or a wrapper that
  tests the exit code is told the restore succeeded.
- `backup_galera` no longer stops when `mysqldump` fails: the truncated
  output is renamed from `.tmp` to its final name and the Job succeeds.
- The exit handler of `restore_galera`, which should put the Service
  back when the script dies, contains `{$target_pod}` (braces misplaced):
  it would point the Service at a pod named `{<pod>}`, that is, at
  nothing. The bug is hidden today because, with errexit off, the script
  rarely dies early.

## Why it matters in production

- A restore is run on a bad day. An exit code that says "done" after a
  dump that stopped at the first SQL error leaves a database with some
  tables from the backup and some current ones, and nobody is warned.
- A backup Job that succeeds with a truncated dump is worse than a Job
  that fails: monitoring of Job status (the usual way to watch backups
  on Kubernetes) stays green.
- Fixing only the `set +eu` leak would arm the malformed exit handler:
  the first failed restore would then leave the database Service without
  endpoint. The three changes must be reviewed together, which is the
  kind of detail an operator's eye catches.

## Evidence from the lab

Lab: mariadb-operator shipped with `openstack-operator.v0.8.0`
(18-stable catalog), restore run with the script in a restore pod on
2026-11-12, file deliberately invalid:

```text
Disable traffic to Galera cluster openstack-cell1
Restore content: all
Restore backup /tmp/bad.sql into Galera pod openstack-cell1... FAILED
Restore traffic to Galera cluster openstack-cell1 via endpoint openstack-cell1-galera-0
ERROR 1064 (42000) at line 1: You have an error in your SQL syntax; ...
rc=0
```

Recorded in
[what happens when a restore file fails to load](../../docs/knowledge-base/backup-and-restore-drills.md#what-happens-when-a-restore-file-fails-to-load).
A local simulation on 2026-11-13 (a script with `set -eu` that sources a
file containing `set +eu`, then runs a failing command) confirmed that
the script continues, and exits non-zero when the sourced line is
removed.

**Not verified on the lab:**

- A backup with a failing `mysqldump` was not provoked; the statement
  about truncated dumps comes from reading the script.
- The malformed exit handler was never executed on the lab (the
  endpoint was always restored by the normal path).
- Nothing was run against a build of `main`.

## Upstream state

Repository `openstack-k8s-operators/mariadb-operator`, commit
`1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3` (`main`, 2026-11-07), read on
2026-11-13; same logic on `18-stable`
(`22523fe6b6d8d27c9e13a8ce52aaa3e8bc52f8bd`).

| What | Where |
| --- | --- |
| `set +eu` at the top of a file meant to be sourced | [`templates/galera/bin/mysql_root_auth.sh` L2](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galera/bin/mysql_root_auth.sh#L2) |
| Sourced by the backup script after its own `set -eu` (L3) | [`templates/galerabackup/bin/backup_galera` L167](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/backup_galera#L167) |
| Dump pipelines, then unconditional rename of `.tmp` files | [same file, L258-L270](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/backup_galera#L258-L270) |
| Sourced by the restore script after its own `set -eu` (L3) | [`templates/galerabackup/bin/restore_galera` L125](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/restore_galera#L125) |
| Restore loop: `FAILED` is logged, nothing is remembered, no exit code | [same file, L177-L184](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/restore_galera#L177-L184) |
| Exit handler: `set_endpoint ${service} {$target_pod}` | [same file, L58](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/restore_galera#L58) |

The restore loop tests `$?` after the pipeline, which shows the author
expected the script to continue past a failed file (otherwise errexit
would have ended it before the test). So "continue with the next file"
may be intended; "exit 0 at the end" is unlikely to be.

Duplicate search (GitHub search API, issues and pull requests, open and
closed, same repository, 2026-11-13): `restore_galera`, `backup_galera`,
`mysql_root_auth`, `"set +eu"`, `restore in:title` — no report and no
fix found. Related history: pull requests #400 (GaleraRestore,
2026-01), #433 (the `--content` flag) and #493 (the SST retry). The `OSPRH` Jira project
was not searched.

Not specific to the lab.

## Proposed contribution

One pull request against `main`, three commits or one, as reviewers
prefer:

1. `restore_galera`: remember that a file failed and exit non-zero at
   the end, after the Service endpoint has been restored. Test the
   pipeline with `if ! … ; then`, which works with or without errexit.
2. `restore_galera`: fix the exit handler argument (`"${target_pod}"`).
3. Stop the leak of `set +eu`: either restore the caller's options after
   sourcing (`set -eu` again in both callers, the smallest change), or
   make `mysql_root_auth.sh` save and restore the options. The file is
   also sourced by the account and database scripts and by the Galera
   start scripts (`templates/account.sh`, `templates/database.sh`,
   `templates/galera/bin/mysql_bootstrap.sh` and others), which may rely
   on the relaxed mode, so the caller-side change is the safer first proposal.
4. `backup_galera`: with errexit back, check that every later command
   that may legitimately fail is guarded (the script was only ever run
   in relaxed mode after line 167; an unguarded `grep` or `test` would
   now abort the backup). This audit is the real work of the change.
5. Chainsaw: a negative restore test (an invalid file; the pod or the
   command must fail, and the Service must have its endpoint back).

## Reproduction and validation plan

1. **[READ-ONLY]** Dump the three scripts from the running pods and
   compare with the pointers above.
2. **[CHANGE]** Replay the failed-file restore on the cell database with
   an invalid file and `--content data` (already done once: no data
   change, the endpoint is removed and put back); record `rc`.
3. **[CHANGE]** With the patched `restore_galera` copied into a debug
   restore pod: same test, expect `FAILED`, endpoint restored, non-zero
   exit. Then kill the script between "Disable traffic" and the end
   (`kill -TERM`) and check that the exit handler restores the selector
   (this is the path that has never run).
4. **[CHANGE]** With the patched `backup_galera`: one normal backup (must
   still succeed: proves the audit of step 4 above), then one with the
   dump made to fail (for instance a wrong socket path through a
   modified copy) and check that no final file is created.
5. Project checks: `pre-commit run --all-files`, `make test`, chainsaw
   `backup-capture` and `restore` suites on a scratch cluster.

Keep the repair command of the knowledge-base entry at hand during
steps 2 and 3: an interrupted restore leaves the Service without
endpoint.

## Effort and risk

- Effort: one to two days; the audit of `backup_galera` under errexit
  and the chainsaw runs dominate.
- Risk: medium. Re-enabling errexit in a script that has never run with
  it can turn a harmless non-zero status into a failed nightly backup.
  If the audit is not conclusive, send only items 1, 2 and 5 (restore
  side) first, and open the backup side as a question.
- Review risk: the maintainers may prefer their own fix; a precise
  report already has value (see the methodology, "what happens to
  outside reports").

## Review-readiness checklist

- [ ] Failed-restore exit code reproduced again, output saved.
- [ ] Exit handler path exercised with the fix, output saved.
- [ ] Normal backup and normal restore still pass with the fix.
- [ ] Negative chainsaw test added and passing.
- [ ] Pointers re-read at the tip of `main` on the day of sending.
- [ ] Duplicate search repeated.
- [ ] `pre-commit` clean; commit messages explain the interaction
      between the three changes.
- [ ] Journal entry written.

## Open questions

- Is "continue with the next file after a failure" the intended
  behaviour of the restore loop? The draft keeps it and only changes the
  final exit code.
- Does any other caller of `mysql_root_auth.sh` depend on the relaxed
  shell options?
- Who consumes the exit code: the `GaleraRestore` resource only creates
  a pod that sleeps (`internal/mariadb/backup/restorepod.go` L48); the
  person runs the script with `oc exec`
  (`docs/backup-restore.md` L214-L219). The exit code therefore matters
  to people and to their wrappers, not to a controller.

## Draft pull request text

Title:

```text
restore_galera: return an error when a backup file fails to load
```

Body:

```markdown
`restore_galera` and `backup_galera` start with `set -eu` and then source
`mysql_root_auth.sh`, which begins with `set +eu`. Since the file is
sourced, errexit and nounset stay disabled for the rest of both scripts.

Visible effect on restore: a file that fails to load is reported as
`FAILED`, and the script exits with 0.

    Restore backup /tmp/bad.sql into Galera pod openstack-cell1... FAILED
    Restore traffic to Galera cluster openstack-cell1 via endpoint openstack-cell1-galera-0
    ERROR 1064 (42000) at line 1: You have an error in your SQL syntax; ...
    $ echo $?
    0

This change:

- makes `restore_galera` exit non-zero when at least one file failed,
  after the Service endpoint has been restored (the loop still tries the
  remaining files, as before);
- fixes the argument of the exit handler (`{$target_pod}` ->
  `"${target_pod}"`), which would otherwise have pointed the Service at
  a non-existent pod name when the script is interrupted;
- re-enables `set -eu` after sourcing `mysql_root_auth.sh` in both
  scripts <or: restore side only, see below>;
- adds a chainsaw test restoring an invalid file.

Tested on a single-node deployment: <paste before/after>.

Note for reviewers: with errexit back in `backup_galera`, a failing
`mysqldump` now aborts the Job instead of publishing a truncated dump.
I went through the commands after the `source` line and guarded
<list>. If you prefer to handle the backup script separately, I can
split it out.
```

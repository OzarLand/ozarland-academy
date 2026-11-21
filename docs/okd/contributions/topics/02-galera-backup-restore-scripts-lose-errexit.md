# 02 — Galera backup and restore scripts lose `set -e`; a failed restore exits 0

- **Target:** `openstack-k8s-operators/mariadb-operator`, branch `main`
- **Type:** bug fix (shell scripts) + test
- **Effort:** small to medium (three small changes that must go
  together, one negative test)
- **Status:** candidate, lab evidence complete — the three effects
  reproduced on the lab at 18-stable, patched copies of both scripts run
  on the lab; not tried with an operator built from `main`
- **Upstream state checked on:** 2026-11-14

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
  it asks for a selector value `{<pod>}`, which the API refuses as an
  invalid label value; the refusal is not shown (`curl -s -o /dev/null`)
  and the Service stays without endpoint. The bug is hidden today
  because, with errexit off, the script rarely dies early.

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

### Replay with unmodified and patched scripts (2026-11-14)

Versions: `openstack-operator.v0.8.0`; mariadb-operator image
`quay.io/openstack-k8s-operators/mariadb-operator@sha256:4be85fd5…`;
pod image
`quay.io/podified-antelope-centos9/openstack-mariadb@sha256:5316fe09…`
(`mariadb-server-10.5.29-5.el9`, `bash-5.1.8-9.el9`). Both scripts on
the lab are byte-identical to branch `18-stable` (`22523fe6`); `main`
differs only in configuration file paths. A logical dump of both
instances was set aside before the exercise. Instance used:
`openstack-cell1`. "Patched" means the diff of the proposal below,
applied to the lab copy of the script.

Backup, `mysqldump` replaced through `PATH` by a test double that
writes one comment line, prints an error and exits 2 (the script itself
is not modified in the first run):

| Run | Script | Job result | Data file published |
| --- | --- | --- | --- |
| A | unmodified | `Complete`, pod exit code 0 | yes: 87 bytes, one comment line, `gzip -t` passes |
| B | patched | `Failed`, pod exit code 123 | no, and no `.tmp` left |
| C | patched, real `mysqldump` | `Complete`, exit code 0 | yes: valid dump, 110 `CREATE TABLE` |

Run A, Job log:

```text
… backup_galera Preparing a logical backup of the database
mysqldump: Error 2013: Lost connection to server during query (simulated)
… backup_galera Preparing a logical backup of the database's users and grants
… backup_galera Stop the local mariadb server
… backup_galera New backup of Galera cluster openstack-cell1 created successful
… backup_galera Backup of Galera cluster openstack-cell1 finished in 10 seconds (ret: 0)
```

Run B, Job log:

```text
… backup_galera Preparing a logical backup of the database
mysqldump: Error 2013: Lost connection to server during query (simulated)
… backup_galera Backup of Galera cluster openstack-cell1 finished in 9 seconds (ret: 123)
```

Run C shows that the patched script still completes a normal backup
under errexit on this single-member instance (state transfer, dump,
grants, retention).

Restore, run with `oc exec` in the pod of a `GaleraRestore`,
`--content data`, files that change no data:

| Run | Script | File | Output | Exit code | Service afterwards |
| --- | --- | --- | --- | --- | --- |
| R1 | unmodified | invalid SQL | `FAILED` | 0 | endpoint restored |
| R2 | patched | invalid SQL | `FAILED`, then `ERROR: At least one backup file could not be restored…` | 1 | endpoint restored |
| R3 | unmodified | `SELECT SLEEP(20);`, script sent `SIGTERM` after 4 s | handler prints "Restore traffic…" | 0 as seen by the calling shell | **selector empty, no endpoint**, until repaired by hand 22 s later |
| R4 | patched | same, same signal | handler prints "Restore traffic…" | 0 as seen by the calling shell | endpoint restored at once |
| R5 | patched | `SELECT 1;` | `OK` | 0 | endpoint restored |

What the API answers to the value the unmodified handler sends
(server-side dry run of the same patch):

```text
The Service "openstack-cell1" is invalid: spec.selector: Invalid value:
"{openstack-cell1-galera-0}": a valid label must be an empty string or
consist of alphanumeric characters, '-', '_' or '.', …
```

Two side observations of R3 and R4, not part of the proposal: the
`mysql` client started by the script kept running after the script had
died (its output arrived 16 s later), and the calling shell saw exit
status 0 for the interrupted script; the second point was not
investigated.

The Service was repaired after R3 with the command of the
knowledge-base entry; the `GaleraRestore`, the test Jobs, the temporary
ConfigMaps and the files of runs A and C were removed afterwards.

**Not verified on the lab:**

- Nothing was run with an operator built from `main`: the fix ran as
  patched copies of the 18-stable scripts (Jobs with the script mounted
  from a temporary ConfigMap, and a copy in the restore pod).
- The failing dump is a test double, not a real `mysqldump` failure.
- The patched backup ran on a one-member Galera instance only: the
  retry path of the state transfer request and the three-member donor
  selection were not exercised under errexit.
- A restore of real data with the patched script was not run (R5 loads
  `SELECT 1;`).
- The chainsaw suites were not run; the negative restore test is
  described, not written.

## Upstream state

Repository `openstack-k8s-operators/mariadb-operator`, commit
`1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3` (`main`, 2026-11-07), read on
2026-11-13 and again on 2026-11-14 (`main` has not moved); same logic on `18-stable`
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
fix found. Repeated on 2026-11-14 with `restore_galera`,
`backup_galera`, `set +eu`, `errexit`, `mysql_root_auth`,
`restore exit code`, `finalizer_check_endpoint`, `GaleraRestore`
(7 results read), plus the list of the 14 open pull requests and of all
issues: still nothing. Open pull request #610 (cluster TLS profile)
touches `backup_galera` on other lines. Related history: pull requests #400 (GaleraRestore,
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

The change as a diff against `main` at `1a1c03d2`, to apply on top of
the diff of [topic 01](01-galerabackup-retention-deletes-nothing.md)
(both were applied to a scratch clone at that commit; the same changes
are the ones run on the lab):

```diff
--- a/templates/galerabackup/bin/backup_galera
+++ b/templates/galerabackup/bin/backup_galera
@@ -165,6 +165,8 @@ fi
 log "Retrieve user credentials for Galera cluster ${DB}"
 export MYSQL_CONN_PARAMS=$MYSQL_OPTS
 . /var/lib/operator-scripts/mysql_root_auth.sh
+# mysql_root_auth.sh runs "set +eu" in this shell, restore our settings
+set -eu
 dbpass=$MYSQL_PWD
 test -n "$MYSQL_PWD"
 dbuser=root
@@ -194,23 +196,23 @@ while kill -s 0 $joinerpid 2>/dev/null && ! grep -q '^ready ' $JOINER_LOG; do
     sleep 1
 done
 if ! kill -s 0 $joinerpid 2>/dev/null; then
-    wait $joinerpid
-    res=$?
+    res=0
+    wait $joinerpid || res=$?
     err "joiner SST script returned error ${res}, backup of Galera cluster ${DB} failed"
 fi
-kill $tailpid 2>/dev/null
+kill $tailpid 2>/dev/null || true
 
 # Start a backup by requesting a SST with garbd
 # Use a retry logic until the SST request is successful or
 # too many retries have been performed
 retries=$SST_RETRIES
-garbd_select_target_and_trigger_sst
-res=$?
+res=0
+garbd_select_target_and_trigger_sst || res=$?
 while [ $res -ne 0 -a $retries -gt 0 ]; do
     warn "Could not trigger SST, retrying"
     sleep $SST_WAIT
-    garbd_select_target_and_trigger_sst
-    res=$?
+    res=0
+    garbd_select_target_and_trigger_sst || res=$?
     retries=$((retries - 1))
 done
 
--- a/templates/galerabackup/bin/restore_galera
+++ b/templates/galerabackup/bin/restore_galera
@@ -1,6 +1,7 @@
 #!/bin/bash
 
 set -eu
+set -o pipefail
 
 # API server config
 APISERVER=https://kubernetes.default.svc
@@ -13,6 +14,7 @@ SERVICEACCOUNT=/var/run/secrets/kubernetes.io/serviceaccount
 confirm=
 content=all
 target_pod=
+failed=0
 
 
 # Helper functions
@@ -55,7 +57,7 @@ function set_endpoint() {
 function finalizer_check_endpoint {
     if [ -n "${target_pod}" ]; then
         log "Restore traffic to Galera cluster ${DB} via endpoint ${target_pod}"
-        set_endpoint ${service} {$target_pod}
+        set_endpoint "${service}" "${target_pod}"
     fi
 }
 
@@ -123,6 +125,8 @@ fi
 log "Retrieve user credentials for Galera cluster ${DB}"
 export MYSQL_CONN_PARAMS=$MYSQL_OPTS
 . /var/lib/operator-scripts/mysql_root_auth.sh
+# mysql_root_auth.sh runs "set +eu" in this shell, restore our settings
+set -eu
 dbpass=$MYSQL_PWD
 test -n "$MYSQL_PWD"
 dbuser=root
@@ -175,11 +179,11 @@ for backup in $*; do
         READ=cat
     fi
     log_n "Restore backup ${backup} into Galera pod ${DB}..."
-    $READ ${backup} | mysql $MYSQL_OPTS -u$dbuser -p$dbpass -h$target_pod_fqdn
-    if [ $? -eq 0 ]; then
+    if $READ ${backup} | mysql $MYSQL_OPTS -u$dbuser -p$dbpass -h$target_pod_fqdn; then
         log_status "OK"
     else
         log_status "FAILED"
+        failed=1
     fi
 done
 
@@ -187,3 +191,7 @@ log "Restore traffic to Galera cluster ${DB} via endpoint ${target_pod}"
 set_endpoint "${service}" "${target_pod}"
 # no need to run finalizer past this point
 target_pod=
+
+if [ "${failed}" -ne 0 ]; then
+    err "At least one backup file could not be restored into Galera cluster ${DB}"
+fi
```

Result of the audit of `backup_galera` under errexit (item 4): three
places returned a status that the script reads afterwards with `$?` and
would have ended the script before the reading — the `wait` on the
joiner, the two calls of the state transfer function (the retry loop
would never have run) — and one `kill` of a process that may already be
gone. They are guarded in the diff. `set -o pipefail` is added to
`restore_galera` so that a file that cannot be decompressed counts as a
failure; `backup_galera` already sets it.

How to test it in the target repository:

- Existing tests: chainsaw `restore` (two instances, backup then
  restore of valid files) and `backup-capture`; none restores an
  invalid file or makes a dump fail. The Go suites do not run the shell
  templates.
- Checks run locally on 2026-11-14 in a scratch clone of `main` with
  both diffs applied: the `bashate` hook of `.pre-commit-config.yaml`
  (version 2.1.1, same arguments) passes on both scripts;
  `go test ./...` in `api/` and at the root (envtest 1.33, Go 1.26.3)
  passes.
- Not run: `make test` as such (no `make` on the workstation; the two
  `go test` commands are what it runs), `golangci-lint`, and the
  chainsaw suites
  (`chainsaw test --config test/chainsaw/config.yaml test/chainsaw/tests/restore`
  against a cluster running the operator built from the branch).

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

- [x] Failed-restore exit code reproduced again, output saved
      (2026-11-14, R1).
- [x] Exit handler path exercised without and with the fix, output
      saved (2026-11-14, R3 and R4).
- [x] Normal backup still passes with the fix (2026-11-14, run C).
- [ ] Normal restore of real backup files with the fix (only a trivial
      file was loaded, R5).
- [ ] Patched backup on a three-member instance.
- [ ] Negative chainsaw test added and passing.
- [ ] Pointers re-read at the tip of `main` on the day of sending.
- [ ] Duplicate search repeated.
- [ ] `pre-commit` clean; commit messages explain the interaction
      between the three changes.
- [x] Journal entry written (2026-11-14).

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
  `"${target_pod}"`): the API refuses the value with braces as an
  invalid label, so an interrupted restore left the Service without
  endpoint;
- re-enables `set -eu` after sourcing `mysql_root_auth.sh` in both
  scripts <or: restore side only, see below>;
- adds a chainsaw test restoring an invalid file.

Tested on a single-node deployment of the 18-stable operators, with
patched copies of the scripts: an invalid file now gives exit code 1
with the endpoint restored; a restore interrupted by SIGTERM puts the
endpoint back (it stayed empty before); a backup whose `mysqldump`
fails ends as a failed Job without publishing a file (it published an
87-byte file and succeeded before); a normal backup still completes.

Note for reviewers: with errexit back in `backup_galera`, a failing
`mysqldump` now aborts the Job instead of publishing a truncated dump.
I went through the commands after the `source` line and guarded the
`wait` on the joiner, the two calls of
`garbd_select_target_and_trigger_sst` (their status is read with `$?`)
and the `kill` of the `tail` process. I could only run it on a
one-member cluster. If you prefer to handle the backup script separately, I can
split it out.
```

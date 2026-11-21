---
title: "01 — GaleraBackup retention never deletes a backup file"
description: "GaleraBackup.spec.retention is documented as \"delete backup files older than this duration\"."
---

# 01 — GaleraBackup `retention` never deletes a backup file

- **Target:** `openstack-k8s-operators/mariadb-operator`, branch `main`
  (then cherry-pick to the maintained 18.0 branches by the maintainers)
- **Type:** bug fix (shell script) + test + documentation alignment
- **Effort:** small (a few lines of shell, one test case)
- **Status:** candidate, lab evidence complete — reproduced on the lab
  at 18-stable with `retention` set, fix run on the lab as a patched
  copy of the script; not tried with an operator built from `main`
- **Upstream state checked on:** 2026-11-14

## Summary

`GaleraBackup.spec.retention` is documented as "delete backup files older
than this duration". The backup script only *prints* the files it finds
(`find … -print -prune`, no `-delete`), and it looks for names ending in
`.sql` starting with the Galera resource name, while the files it writes
are always named `openstack_backup_<timestamp>.sql.gz` and
`openstack_backup-grants_<timestamp>.sql.gz`. Nothing is ever deleted:
the backup volume fills up at the rate of one dump per run.

## Why it matters in production

- The backup volume is a fixed-size claim. A daily dump of a real cloud
  (tens of GB compressed for Nova, Neutron, Keystone with years of
  history) fills it in weeks; from then on **every backup fails** and
  the operator who trusted `retention: 72h` discovers it the day a
  restore is needed.
- The failure is silent until the volume is full: the Job succeeds and
  logs "Removing previous backups … older than N minutes".
- With local volumes that do not enforce their size (the lab's case),
  the dumps fill the node filesystem instead, which is the disk etcd
  uses.

## Evidence from the lab

- Lab: mariadb-operator shipped with `openstack-operator.v0.8.0`
  (18-stable catalog), two Galera instances (`openstack`,
  `openstack-cell1`), one `GaleraBackup` each.
- The script deployed in the backup pod was dumped on 2026-11-12 and
  contains the lines quoted below (evidence file
  `kb3/02-restore-crd-scripts.txt`, kept outside the repository).
- Five dumps per instance had accumulated after 14 hours of manual runs;
  recorded in
  [the restore drill entry](../../docs/knowledge-base/backup-and-restore-drills.md).
- A local simulation of the `find` expression on a scratch directory
  (2026-11-13) printed only a file named exactly `<db>….sql` and deleted
  nothing.

### Reproduction with `retention` set (2026-11-14)

Versions: `openstack-operator.v0.8.0`; mariadb-operator image
`quay.io/openstack-k8s-operators/mariadb-operator@sha256:4be85fd5…`;
backup pod image
`quay.io/podified-antelope-centos9/openstack-mariadb@sha256:5316fe09…`
(`mariadb-server-10.5.29-5.el9`, `findutils-4.8.0-7.el9`). The
`backup_galera` deployed on the lab is byte-identical to branch
`18-stable` (`22523fe6`); `main` differs only in three configuration
file paths, not in the lines discussed here.

Three marker files dated 2026-08-01 were placed on the backup volume of
`openstack-cell1`: two with the real naming (`.sql.gz`) and one whose
name matches the pattern of the script (`<instance>….sql`). Then:

```console
$ oc patch galerabackup openstack-cell1 --type=merge -p '{"spec":{"retention":"10m"}}'
$ oc get cronjob backup-openstack-cell1 -o jsonpath='{…env[?(@.name=="RETENTION")]}'
{"name":"RETENTION","value":"10"}
$ oc create job --from=cronjob/backup-openstack-cell1 test-retention
$ oc logs job/test-retention | tail -4
… backup_galera New backup of Galera cluster openstack-cell1 created successful
… backup_galera Removing previous backups of Galera cluster openstack-cell1 which are older than '10' minutes
/backup/data/openstack-cell1_marker.sql
… backup_galera Backup of Galera cluster openstack-cell1 finished in 10 seconds (ret: 0)
```

Volume content after the Job (10:23 UTC), nothing removed — neither the
August markers, nor the dumps of the previous days, nor the file the
script printed:

```text
openstack_backup_2026-08-01_00-00-00.sql.gz          2026-08-01 00:00   marker
openstack_backup_2026-11-13_00-00-01.sql.gz          2026-11-13 00:00
openstack_backup_2026-11-13_05-46-13.sql.gz          2026-11-13 05:46
openstack_backup_2026-11-14_07-44-26.sql.gz          2026-11-14 07:44
openstack_backup_2026-11-14_10-22-51.sql.gz          2026-11-14 10:23   new
openstack_backup-grants_2026-08-01_00-00-00.sql.gz   2026-08-01 00:00   marker
openstack_backup-grants_2026-11-13_00-00-01.sql.gz   2026-11-13 00:00
…
openstack-cell1_marker.sql                           2026-08-01 00:00   marker, printed, kept
```

### The proposed line on the lab (2026-11-14)

A copy of the script carrying the change below was run as a Job built
from the CronJob (same image, same volume, script mounted from a
temporary ConfigMap), with `retention` back to the lab value (72 h,
`RETENTION=4320`):

```text
… backup_galera Removing previous backups of Galera cluster openstack-cell1 which are older than '4320' minutes
/backup/data/openstack_backup-grants_2026-08-01_00-00-00.sql.gz
/backup/data/openstack_backup_2026-08-01_00-00-00.sql.gz
… backup_galera Backup of Galera cluster openstack-cell1 finished in 10 seconds (ret: 0)
```

The two August markers were gone, every dump younger than 72 hours was
still there, the new dump was valid (`gzip -t`, 110 `CREATE TABLE`,
`-- Dump completed`). The marker named `<instance>….sql` is not touched
by the new pattern.

The temporary-file pattern of the exit handler was checked in the same
pod: with `DB=openstack-cell1`, `rm -f ${BACKUP_DIR}/${DB}_backup*.tmp`
leaves `openstack_backup_….sql.gz.tmp` in place; with `DB=openstack` it
removes it.

All markers, test Jobs, the ConfigMap and the test dumps were removed
afterwards; `retention` is back to `72h0m0s`.

**Not verified on the lab:**

- Nothing was run with an operator built from `main`: the fix ran as a
  patched copy of the 18-stable script. The diff below applies cleanly
  to `main`.
- The chainsaw suites were not run (they need a cluster running an
  operator built from the branch); the proposed chainsaw step is
  described, not written.
- `retention` was exercised through manual Jobs created from the
  CronJob, not through a scheduled run.

## Upstream state

All pointers: repository `openstack-k8s-operators/mariadb-operator`,
commit `1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3` (`main`, 2026-11-07),
read on 2026-11-13 and again on 2026-11-14 (`main` has not moved).
Branch `18-stable`
(`22523fe6b6d8d27c9e13a8ce52aaa3e8bc52f8bd`) has the same lines.

| What | Where |
| --- | --- |
| Retention step, prints and prunes only | [`templates/galerabackup/bin/backup_galera` L278-L281](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/backup_galera#L278-L281) |
| File names, prefix `openstack_backup` hard-coded, suffix `.sql.gz` | [same file, L126-L127](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/backup_galera#L126-L127) |
| Cleanup of temporary files uses `${DB}_backup*.tmp`, which matches only when the Galera resource is named `openstack` | [same file, L54](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/templates/galerabackup/bin/backup_galera#L54) |
| Documentation: "Setting `retention` … causes the backup job to delete files older than that duration" | [`docs/backup-restore.md` L95-L113](https://github.com/openstack-k8s-operators/mariadb-operator/blob/1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3/docs/backup-restore.md#L95-L113) |
| API field `Retention *metav1.Duration` | `api/v1beta1/galerabackup_types.go` L37-L39 |
| Conversion to minutes, environment variable `RETENTION` | `internal/mariadb/backup/cronjob.go` L44-L60 |
| Tests: `backup-capture`, `backup-configs`, `restore`; none sets `retention` | `test/chainsaw/tests/` |

The retention line, verbatim:

```bash
find "${BACKUP_DIR}" -name "${DB}*.sql" -mmin "+${RETENTION}" -print -prune
```

Duplicate search (GitHub search API, issues and pull requests, open and
closed, repository `openstack-k8s-operators/mariadb-operator`,
2026-11-13): `retention`, `backup_galera`, `backup in:title`,
`GaleraBackup` — no report and no fix found. Repeated on 2026-11-14
with `retention`, `backup retention find`, `backup_galera`, `prune`,
`GaleraBackup` (13 results read), plus the list of the 14 open pull
requests and of all issues: still nothing. Open pull request #610
(cluster TLS profile) touches `backup_galera` on other lines; a rebase
may be needed depending on which merges first. Related history:
pull request #325 introduced GaleraBackup (2025-05), #422 added the
custom timestamp, #433 the `--content` flag of the restore. The Red Hat
Jira project (`OSPRH`) that the maintainers reference in commit trailers
was **not** searched (no account used); a ticket may exist there.

Not specific to the lab: the lines are in the upstream template and do
not depend on topology.

## Proposed contribution

One pull request against `main`:

1. Make the retention step delete what the script creates, and nothing
   else:

   ```bash
   find "${BACKUP_DIR}" -maxdepth 1 -type f \
       -name 'openstack_backup*.sql.gz' -mmin "+${RETENTION}" -print -delete
   ```

2. Fix the temporary-file cleanup pattern in `finally` so that it matches
   the real names for any Galera resource name
   (`openstack_backup*.sql.gz.tmp`).
3. Add a chainsaw step that sets `retention`, creates an old file
   (`touch -d`) on the backup volume, runs a backup Job and asserts the
   old file is gone and the new one is present. The existing
   `BACKUP_TIMESTAMP` override (pull request #422) shows the maintainers
   already accept test hooks of this kind.
4. Leave the documentation as is: the code is brought to the documented
   behaviour.

Points 1 and 2 as a diff against `main` at `1a1c03d2` (the diff was
applied to a scratch clone at that commit; the same two changes are the
ones run on the lab):

```diff
--- a/templates/galerabackup/bin/backup_galera
+++ b/templates/galerabackup/bin/backup_galera
@@ -51,7 +51,7 @@ function finally() {
     timefmt=$(date -d "@$SECONDS" -u +'%H hours %M minutes %S seconds' | sed -e 's/00 [^ ]* //g' -e 's/0\([0-9]\)/\1/g')
     log "Backup of Galera cluster ${DB} finished in ${timefmt} (ret: ${last_status})"
     # do not leave incomplete dumps behind
-    rm -f ${BACKUP_DIR}/${DB}_backup*.tmp
+    rm -f "${BACKUP_DIR}"/openstack_backup*.tmp
 }
 
 function garbd_select_target_and_trigger_sst() {
@@ -277,5 +277,5 @@ log "New backup of Galera cluster ${DB} created successful"
 
 if [ -n "${RETENTION}" ]; then
     log "Removing previous backups of Galera cluster ${DB} which are older than '$RETENTION' minutes"
-    find "${BACKUP_DIR}" -name "${DB}*.sql" -mmin "+${RETENTION}" -print -prune
+    find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'openstack_backup*.sql.gz' -mmin "+${RETENTION}" -print -delete
 fi
```

How to test it in the target repository:

- No existing test covers the retention: the Go suites
  (`api/v1beta1`, `internal/controller`, `test/functional`) do not run
  the shell templates, and the chainsaw `restore` test removes old files
  itself with `find … -delete` (`test/chainsaw/tests/restore/chainsaw-test.yaml`
  L138-L139). The commented-out check in
  `test/chainsaw/common/backup-assert.sh` looks for
  `${cluster}*${backup_tag}*.sql.*`, a naming the script does not use.
- Checks run locally on 2026-11-14 in a scratch clone of `main` with the
  diff applied (together with the diff of topic 02): the `bashate` hook
  of `.pre-commit-config.yaml` (version 2.1.1, same arguments) passes;
  `go test ./...` in `api/` and at the root (envtest 1.33, Go 1.26.3)
  passes — as expected, since these do not exercise the script.
- Not run: `make test` as such (no `make` on the workstation; the two
  `go test` commands are what it runs), `golangci-lint`, and the
  chainsaw suites `backup-capture`, `backup-configs`, `restore`
  (`chainsaw test --config test/chainsaw/config.yaml test/chainsaw/tests/<suite>`
  against a cluster running the operator built from the branch).

Design point to raise in the pull request rather than decide alone: the
file prefix is `openstack_backup` for every instance, so the sentence
"only backup files for the same cluster are affected" holds only because
each GaleraBackup has its own volume. If a shared volume is a supported
case, the file name should carry the instance name; that is a behaviour
change and should be the maintainers' call.

## Reproduction and validation plan

1. **[READ-ONLY]** List the backup volume content of one instance and
   the script in the pod; record names, dates and the retention line.
2. **[CHANGE]** Set `retention: 10m` on one `GaleraBackup`, trigger two
   manual Jobs 15 minutes apart
   (`oc create job --from=cronjob/backup-<instance> …`), record the Job
   log and the volume content: the first dump must still be there
   (bug reproduced on the lab version).
3. **[CHANGE]** Build the operator from `main` with the fix (see the
   methodology for `make` targets), or, as a cheaper first check, run
   the fixed script by hand in a debug copy of the backup pod; record
   that the old dump is deleted and the new one kept.
4. Run the project's checks locally: `pre-commit run --all-files`,
   `make test`, and the chainsaw backup tests on a scratch cluster.
5. **[CHANGE]** Put `retention` back to the lab's value.

## Effort and risk

- Effort: half a day including the test; most of it is running the
  chainsaw suite once.
- Risk: a deletion pattern that is too wide destroys backups. Mitigation:
  `-maxdepth 1 -type f`, the literal prefix, and the test.
- Review risk: low; the documentation already states the intended
  behaviour.

## Review-readiness checklist

- [x] Bug reproduced on the lab with `retention` set (step 2), output
      saved (2026-11-14).
- [x] Fix verified as a patched script on the lab (step 3, cheaper
      variant), output saved (2026-11-14).
- [ ] Still present on `main` on the day of sending (re-read the three
      pointers above at the new commit; last done 2026-11-14).
- [ ] Duplicate search repeated on the day of sending (last done
      2026-11-14).
- [ ] Chainsaw step written and passing on a scratch cluster.
- [ ] `pre-commit` clean (only the `bashate` hook and the Go tests were
      run, 2026-11-14).
- [ ] Commit message follows the repository's habit (short subject, body
      explaining the why; see the methodology).
- [x] Journal entry written (2026-11-14).

## Open questions

- Is a Jira ticket expected for a fix of this size from an outside
  contributor, or does the pull request suffice? Recent merged pull
  requests carry a `Jira: OSPRH-…` trailer, but those are written by the
  team.
- Should the file name carry the instance name (see the design point)?
- Which maintained branches get the cherry-pick is the maintainers'
  decision (`/cherry-pick` is theirs to issue).

## Draft pull request text

Title:

```text
Fix GaleraBackup retention: old backup files were never deleted
```

Body:

```markdown
The retention step of `backup_galera` never removed anything:

- it ran `find … -print -prune`, without `-delete`;
- it matched `${DB}*.sql`, while the script writes
  `openstack_backup_<timestamp>.sql.gz` and
  `openstack_backup-grants_<timestamp>.sql.gz`.

`docs/backup-restore.md` states that `retention` deletes backup files
older than the given duration, so this change brings the script to the
documented behaviour: the retention step now deletes regular files named
`openstack_backup*.sql.gz` at the top of the backup directory that are
older than `RETENTION` minutes.

The cleanup of temporary files in the exit handler had the same naming
mismatch (`${DB}_backup*.tmp` only matches when the Galera resource is
named `openstack`); it now uses the real file names.

A chainsaw step covers the retention: it creates an aged file on the
backup volume, runs a backup with `retention` set and checks that the
aged file is gone and the new backup is present.

Observed on a single-node deployment of the 18-stable operators: backup
files accumulated on the volume across runs. Reproduced with
`retention: 10m` (`RETENTION=10`): files dated three months earlier
were still on the volume after the Job, and the Job log printed only a
file named `<instance>….sql`. With the patched script the aged
`openstack_backup*.sql.gz` files were removed and recent ones kept.

Question for reviewers: all instances use the `openstack_backup` prefix,
so two GaleraBackup resources sharing one volume would prune each
other's files. I kept the naming unchanged; tell me if you would rather
have the instance name in the file name.
```

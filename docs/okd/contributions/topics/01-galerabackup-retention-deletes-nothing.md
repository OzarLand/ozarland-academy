# 01 — GaleraBackup `retention` never deletes a backup file

- **Target:** `openstack-k8s-operators/mariadb-operator`, branch `main`
  (then cherry-pick to the maintained 18.0 branches by the maintainers)
- **Type:** bug fix (shell script) + test + documentation alignment
- **Effort:** small (a few lines of shell, one test case)
- **Status:** candidate — read in the code and observed on the lab at
  18-stable; not yet reproduced with a `retention` value set, not yet
  tried against `main`
- **Upstream state checked on:** 2026-11-13

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

**Not verified on the lab:**

- No run with `retention` set to a short value and files older than it
  was recorded: the conclusion comes from the code and from the
  simulation, not from an observed CronJob run. This is the first thing
  to do (see the plan).
- Nothing was run against a build of `main`.

## Upstream state

All pointers: repository `openstack-k8s-operators/mariadb-operator`,
commit `1a1c03d292f54ddb90f5ef2a4e80ec53ea2287c3` (`main`, 2026-11-07),
read on 2026-11-13. Branch `18-stable`
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
`GaleraBackup` — no report and no fix found. Related history:
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

- [ ] Bug reproduced on the lab with `retention` set (step 2), output
      saved.
- [ ] Fix verified (step 3), output saved.
- [ ] Still present on `main` on the day of sending (re-read the three
      pointers above at the new commit).
- [ ] Duplicate search repeated on the day of sending.
- [ ] Test added and passing locally.
- [ ] `pre-commit` clean.
- [ ] Commit message follows the repository's habit (short subject, body
      explaining the why; see the methodology).
- [ ] Journal entry written.

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
`retention: 10m`: <paste the two listings>.

Question for reviewers: all instances use the `openstack_backup` prefix,
so two GaleraBackup resources sharing one volume would prune each
other's files. I kept the naming unchanged; tell me if you would rather
have the instance name in the file name.
```

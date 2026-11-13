# 04 — `edpm_bootstrap` hides a failed package installation on CentOS Stream (fixed on `main`, not on `18-stable`)

- **Target:** `openstack-k8s-operators/edpm-ansible`, branch `18-stable`
  (backport of a change already merged on `main`)
- **Type:** backport request, or backport pull request
- **Effort:** small (cherry-pick of one task file; the work is the
  justification and the test)
- **Status:** candidate — failure observed on the lab at 18-stable; fix
  read on `main`; absence on `18-stable` read in the branch; not retried
  with the fix
- **Upstream state checked on:** 2026-11-13

## Summary

On `18-stable`, the task that installs the bootstrap packages of a data
plane node only fails when the distribution is `redhat`. On CentOS
Stream, the base of the community images, a `dnf` failure (repository
unreachable, wrong proxy, GPG problem) is reported as success. The play
goes on and stops much later on a task that has nothing to do with the
cause; on the lab it was "Import any existing LVM devices" with return
code 2, because `lvm2` had never been installed.

The condition was removed on `main` in August 2026 together with a
stricter `rpm -V` check. The stable branch, which is what the community
catalog installs, still has the old condition.

## Why it matters in production

- The first deployment of a node is where repository and proxy problems
  show up. The error the operator reads must be the `dnf` one.
- A masked failure costs hours: the visible error points at LVM, the
  real cause is three tasks earlier and green.
- CentOS Stream is the only platform community users of the 18-stable
  operators can run; they are the ones who get the masked behaviour.

## Evidence from the lab

Lab: EDPM node on CentOS Stream 9, `openstack-operator.v0.8.0`
(18-stable catalog). First data plane deployment, recorded in the
validation log (section "Data plane"): the `bootstrap` service failed on
"Import any existing LVM devices" (return code 2); `lvm2` was missing;
`dnf` had failed because the repositories written by `repo-setup` used
plain HTTP, which the lab egress does not relay. The package task had
reported success.

**Not verified on the lab:**

- The task file of the Ansible runner image used that day was not
  extracted; that it matches the `18-stable` branch is assumed from the
  catalog in use.
- The deployment was not replayed with the task from `main`.

## Upstream state

Looked at on 2026-11-13, `main` at `3e5e2930038443693cecd21caab5a50db051d93a`,
`18-stable` at `2317faf8f09ccfddd718baf3933a805840c40051`.

| Fact | Pointer |
| --- | --- |
| `18-stable`: `failed_when` requires `distribution == 'redhat'` and `rc == 1` | [`roles/edpm_bootstrap/tasks/packages.yml` L44-L56](https://github.com/openstack-k8s-operators/edpm-ansible/blob/2317faf8f09ccfddd718baf3933a805840c40051/roles/edpm_bootstrap/tasks/packages.yml#L44-L56) |
| `18-stable`: `rpm -V` only fails when `%verify` is in stderr | same file, L58-L64 |
| `main`: `failed_when` is `rc != 0` for every distribution; `rpm -V --noconfig` fails on any non-zero return code | [`packages.yml` L44-L65 on `main`](https://github.com/openstack-k8s-operators/edpm-ansible/blob/3e5e2930038443693cecd21caab5a50db051d93a/roles/edpm_bootstrap/tasks/packages.yml#L44-L65) |
| Fix on `main` | pull request #1244, commit `fc469ac784456cafea20e2e05bf0f3d5c2eb9cd3`, merged 2026-08-17, references Jira OSPRH-33601; a later change to the same file in #1306 |
| Also absent from the feature-release branches `18.0-fr5` to `18.0-fr7`; present on `19.0-beta` | same file on those branches |
| How backports reach `18-stable` | either the cherry-pick robot (pull request #1313, opened by `openshift-cherrypick-robot`) or a manual pull request titled `[18-stable] ...` with the original text and a `Conflicts:` list (#1338, #1350) |

Duplicate search on 2026-11-13 (issues and pull requests, open and
closed, in `openstack-k8s-operators/edpm-ansible`): "silently ignores
failures", "OSPRH-33601", "failed_when edpm_bootstrap". Only pull
requests #1244 and #1306 came up; no pull request against `18-stable`. The Jira ticket
could not be read without an account: **whether a backport is planned or
was refused there is unknown.**

**Not specific to the lab:** the condition is in the branch; any CentOS
Stream node whose `dnf` fails hits it. The lab only supplied the trigger
(HTTP repositories behind an HTTPS-only egress).

## Proposed contribution

1. Ask first, in an issue on the repository (short, with the pointers
   above): is a backport of #1244 to `18-stable` wanted? The `rpm -V`
   part is stricter than before and maintainers may want only the
   `failed_when` part on a stable branch.
2. If the answer is yes and nobody with rights uses the robot, open a
   manual backport pull request against `18-stable`: `git cherry-pick -x`
   of the commit, title `[18-stable] <original title>`, original
   description kept, `Signed-off-by` added.

This is a good first contact: no design, a change the maintainers wrote
themselves, and a real user report from the platform they do not test
every day.

## Reproduction and validation plan

1. `[READ-ONLY]` Extract the task file from the runner image in use and
   compare it with the branch:
   `oc get osdps bootstrap -o yaml`, then
   `podman run --rm <ansibleee image> cat /usr/share/ansible/collections/ansible_collections/osp/edpm/roles/edpm_bootstrap/tasks/packages.yml`
   (path to confirm in the image).
2. `[CHANGE]` On a spare EDPM node, make `dnf` fail on purpose (disable
   the repositories written by `repo-setup`), run a deployment limited to
   `bootstrap`, record that the package task is green and where the play
   really stops.
3. `[CHANGE]` Same run with the collection built from the backport
   branch (custom runner image, see the `openstack_ansibleee` directory
   of the repository): the package task must fail with the `dnf` message.
4. `[CHANGE]` Normal run with working repositories on the backport
   branch: no regression, in particular the `rpm -V --noconfig` check
   passes on a freshly provisioned CentOS Stream 9 node.
5. Molecule scenario of the role, locally: `make execute_molecule` is the
   documented entry point; confirm the target name in the Makefile of the
   branch before running.

## Effort and risk

- Code: none of our own; a clean cherry-pick is expected (the file is
  nearly identical on both branches), to confirm.
- Risk: the stricter `rpm -V` may fail on nodes where it passed before;
  this is the reason to ask first and to run step 4.
- Reputation: low risk, as long as the request does not present the bug
  as unknown; it is fixed, the question is only the branch.

## Review-readiness checklist

- [ ] Task file of the image in use compared with the branch (step 1)
- [ ] Masked failure reproduced on purpose (step 2)
- [ ] Maintainers agreed on a backport and on its scope
- [ ] Cherry-pick applied with `-x`, conflicts listed if any
- [ ] Steps 3 and 4 done on the lab, results in the journal
- [ ] `make linters` and the molecule scenario of the role pass locally
- [ ] Pull request against `18-stable`, title prefixed `[18-stable]`

## Open questions

- Is a backport already tracked in Jira (OSPRH-33601)?
- Do external contributors' `/cherry-pick 18-stable` comments work on
  this repository, or only members'? Not tested (nothing is posted
  upstream during preparation).
- Does the community catalog follow `18-stable` or a feature-release
  branch for the runner image? Determines which branch matters most.

## Draft issue text

> **Title:** Backport "edpm_bootstrap silently ignores package
> installation failures" (#1244) to 18-stable?
>
> On `18-stable`, `roles/edpm_bootstrap/tasks/packages.yml` still fails
> the bootstrap package installation only when the distribution is
> `redhat` (L48-L51 at `2317faf8`). On CentOS Stream 9 a failed `dnf`
> transaction is therefore reported as success; in my deployment the
> play stopped later on "Import any existing LVM devices" (rc=2) because
> `lvm2` was never installed, and the real cause (repositories not
> reachable) was hidden.
>
> This was fixed on `main` by #1244 (`fc469ac7`). Would you accept a
> backport to `18-stable`? I can open the pull request. If the stricter
> `rpm -V --noconfig` check is not wanted on a stable branch, I can limit
> it to the `failed_when` change.

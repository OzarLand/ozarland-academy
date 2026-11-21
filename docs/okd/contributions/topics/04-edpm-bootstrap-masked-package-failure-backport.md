---
title: "04 — edpm_bootstrap hides a failed package installation on CentOS Stream (fixed on main, not on 18-stable)"
description: "On 18-stable, the task that installs the bootstrap packages of a data plane node only fails when the distribution is redhat."
---

# 04 — `edpm_bootstrap` hides a failed package installation on CentOS Stream (fixed on `main`, not on `18-stable`)

- **Target:** `openstack-k8s-operators/edpm-ansible`, branch `18-stable`
  (backport of a change already merged on `main`)
- **Type:** backport request, or backport pull request
- **Effort:** small (cherry-pick of one task file; the work is the
  justification and the test)
- **Status:** candidate, lab evidence complete — the task file of the
  image in use is byte-identical to `18-stable`; the masked failure was
  replayed on purpose on 2026-11-14, and the task text of `main` fails
  as expected on the same node. Not run: the molecule scenario and a
  full bootstrap with a runner image built from the backport
- **Upstream state checked on:** 2026-11-14

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

Runs of 2026-11-14 (10:14 to 10:17 UTC, lab evidence directory
`contrib/04/`, files 01 to 04), on the same lab:

1. **Task file of the image in use.** The `bootstrap` Job runs the
   runner image `openstack-ansibleee-runner@sha256:1fa2a028c04b...`
   (the one listed by the `OpenStackVersion` resource, target
   `0.8.0-1794211973`). Read from a temporary pod of that image,
   `roles/edpm_bootstrap/tasks/packages.yml` of the `osp.edpm`
   collection has the SHA-256 `aa7cb256eb57...4570`: the same as the
   file on `18-stable` at `2317faf8`. It contains the `redhat`
   condition. Files in the image are dated 2026-10-30.
2. **Masked failure, replayed.** A throw-away data plane service
   included the real `packages.yml` of the role from the image, with
   the package list replaced by one name that does not exist. On the
   CentOS Stream 9 node:

   ```text
   TASK [osp.edpm.edpm_bootstrap : Install required packages to bootstrap EDPM] ***
   ok: [edpm-compute-0]
   TASK [osp.edpm.edpm_bootstrap : Ensure packages are actually well installed] ***
   ok: [edpm-compute-0]
   ...
   "distribution": "CentOS", "dnf_failed": false, "dnf_rc": 1,
   "dnf_msg": "Failed to install some of the specified packages",
   "dnf_failures": ["No package no-such-package-for-the-demo available."],
   "rpm_verify_rc": 1, "rpm_verify_stderr": "",
   "rpm_verify_stdout": "package no-such-package-for-the-demo is not installed"
   PLAY RECAP: ok=5 changed=0 unreachable=0 failed=0 skipped=1
   ```

   Both tasks are green although `dnf` returned 1 and `rpm -V` returned
   1: the second check is masked too, because "is not installed" goes
   to standard output and the condition looks for `%verify` in the
   error output. The deployment ended "Setup complete".
3. **Task text of `main`, same node.** A second throw-away service
   carried the two tasks as they are on `main` at `3e5e2930` (copied
   inline; `retries` reduced to 1 to keep the run short). With the
   missing package the first task fails with the `dnf` message:

   ```text
   fatal: [edpm-compute-0]: FAILED! => {"attempts": 1, "changed": false,
   "failed_when_result": true,
   "failures": ["No package no-such-package-for-the-demo available."],
   "msg": "Failed to install some of the specified packages", "rc": 1}
   ```

   With the 17 default packages of the role, both tasks pass (`ok=3`,
   `changed=0`).
4. **`rpm -V` on a deployed node.** For the 17 default packages,
   `rpm -V` returns 2 (two configuration files changed by the
   deployment: `nftables.conf`, `NetworkManager.conf`) and
   `rpm -V --noconfig` returns 0. The stricter check of `main` passes
   on this node only thanks to `--noconfig`: the backport must take
   both changes together.

Nothing was installed or changed on the node by these runs; the test
services and deployments were deleted and the NodeSet is Ready.

**Not verified on the lab:**

- A runner image built from the backport branch was not made; the
  fixed tasks were run as inline copies, not from the collection.
- A full `bootstrap` on a freshly provisioned node with the fixed tasks
  was not run (`rpm -V --noconfig` was only checked on a node deployed
  three days earlier).
- The molecule scenario of the role was not run (it needs a container
  engine on the workstation, which is not available).
- A `dnf` failure caused by unreachable repositories (the original
  trigger) was not replayed; the missing package gives the same return
  code through the same module.

## Upstream state

Looked at on 2026-11-14, `main` at `3e5e2930038443693cecd21caab5a50db051d93a`,
`18-stable` at `2317faf8f09ccfddd718baf3933a805840c40051` (both
unchanged since 2026-11-13).

| Fact | Pointer |
| --- | --- |
| `18-stable`: `failed_when` requires `distribution == 'redhat'` and `rc == 1` | [`roles/edpm_bootstrap/tasks/packages.yml` L44-L56](https://github.com/openstack-k8s-operators/edpm-ansible/blob/2317faf8f09ccfddd718baf3933a805840c40051/roles/edpm_bootstrap/tasks/packages.yml#L44-L56) |
| `18-stable`: `rpm -V` only fails when `%verify` is in stderr | same file, L58-L64 |
| `main`: `failed_when` is `rc != 0` for every distribution; `rpm -V --noconfig` fails on any non-zero return code | [`packages.yml` L44-L65 on `main`](https://github.com/openstack-k8s-operators/edpm-ansible/blob/3e5e2930038443693cecd21caab5a50db051d93a/roles/edpm_bootstrap/tasks/packages.yml#L44-L65) |
| Fix on `main` | pull request #1244, commit `fc469ac784456cafea20e2e05bf0f3d5c2eb9cd3`, merged 2026-08-17, references Jira OSPRH-33601; a later change to the same file in #1306 |
| The backport applies without conflict | the two files changed by `fc469ac7` (`tasks/packages.yml`, `molecule/default/verify.yml`) have the same blob on `18-stable` as on the parent of the fix (`1e9dfd32`, `961a85d1`); #1306 (`36a6e0d9`, 2026-10-13, "Skip installed package verification when package list is empty") must follow it |
| Also absent from the feature-release branches `18.0-fr5` to `18.0-fr7`; present on `19.0-beta` | same file on those branches |
| How backports reach `18-stable` | either the cherry-pick robot (pull request #1313, opened by `openshift-cherrypick-robot`) or a manual pull request titled `[18-stable] ...` with the original text and a `Conflicts:` list (#1338, #1350) |

Duplicate search on 2026-11-14 with the GitHub search API
(`repo:openstack-k8s-operators/edpm-ansible <words>`, issues and pull
requests, open and closed):

| Query words | Result |
| --- | --- |
| `silently ignores failures` | 1: #1244 (the fix) |
| `OSPRH-33601` | 1: #1244 |
| `failed_when edpm_bootstrap` | 4: #1244, and #609, #800, #812 (unrelated, 2024) |
| `18-stable edpm_bootstrap packages` | 0 |

One pull request is open against `18-stable` (#1232, dependency
update). No comment on #1244 asks for a cherry-pick. The Jira ticket
could not be read without an account: **whether a backport is planned
or was refused there is unknown.**

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

1. Done on 2026-11-14: task file extracted from the runner image in use
   (temporary pod of the image, `sha256sum` and `cat` of
   `/usr/share/ansible/collections/ansible_collections/osp/edpm/roles/edpm_bootstrap/tasks/packages.yml`)
   and compared with the branch.
2. Done on 2026-11-14, in a lighter form than planned: the real task
   file was run through a throw-away service with a package name that
   does not exist, instead of breaking the repositories of the node.
   Same module, same return code, no change on the node.
3. Done on 2026-11-14 with inline copies of the tasks of `main`. Still
   to do if the maintainers ask for it: the same with the collection
   built from the backport branch (custom runner image, see the
   `openstack_ansibleee` directory of the repository).
4. Partly done: fixed tasks pass on the deployed node. To do: a
   freshly provisioned CentOS Stream 9 node.
5. To do by the sender: molecule scenario of the role
   (`make execute_molecule` runs it in a container;
   `make execute_molecule_local` with a local molecule), and
   `make linters`.

## Effort and risk

- Code: none of our own; a clean cherry-pick is expected (the file is
  nearly identical on both branches), to confirm.
- Risk: the stricter `rpm -V` may fail on nodes where it passed before;
  this is the reason to ask first and to run step 4.
- Reputation: low risk, as long as the request does not present the bug
  as unknown; it is fixed, the question is only the branch.

## Review-readiness checklist

- [x] Task file of the image in use compared with the branch (step 1,
      2026-11-14)
- [x] Masked failure reproduced on purpose (step 2, 2026-11-14)
- [x] Fixed tasks fail with the `dnf` message and pass with the real
      list (inline copies, 2026-11-14)
- [ ] Maintainers agreed on a backport and on its scope
- [ ] Cherry-pick applied with `-x`, conflicts listed if any
- [ ] Steps 3 and 4 done with the built collection, if asked
- [ ] `make linters` and the molecule scenario of the role pass locally
- [ ] Pull request against `18-stable`, title prefixed `[18-stable]`

## Open questions

- Is a backport already tracked in Jira (OSPRH-33601)?
- Do external contributors' `/cherry-pick 18-stable` comments work on
  this repository, or only members'? Not tested (nothing is posted
  upstream during preparation).
- Does the community catalog follow `18-stable` or a feature-release
  branch for the runner image? The file in the image equals the one of
  `18-stable` (2026-11-14), but it is also unchanged on the
  feature-release branches, so this file alone does not tell.

## Draft issue text

> **Title:** Backport "Fix edpm_bootstrap failed_when logic that
> silently ignores failures" (#1244) to 18-stable?
>
> On `18-stable`, `roles/edpm_bootstrap/tasks/packages.yml` still fails
> the bootstrap package installation only when the distribution is
> `redhat` (L48-L51 at `2317faf8`). On CentOS Stream 9 a failed `dnf`
> transaction is therefore reported as success. In my first deployment
> the play stopped later on "Import any existing LVM devices" (rc=2)
> because `lvm2` was never installed, and the real cause (repositories
> not reachable) was hidden.
>
> Reproduced on purpose with the runner image of the 18-stable catalog
> (`openstack-operator.v0.8.0`; the file in the image has the same
> checksum as the branch): running `packages.yml` with a package name
> that does not exist gives `ok` for "Install required packages to
> bootstrap EDPM" (registered `rc: 1`, "Failed to install some of the
> specified packages") and `ok` for "Ensure packages are actually well
> installed" (`rpm -V` rc 1, "is not installed" on stdout).
>
> This was fixed on `main` by #1244 (`fc469ac7`), completed by #1306.
> The two files touched by #1244 are identical on `18-stable` and on
> the parent of the fix, so the cherry-pick is clean. With the tasks of
> `main` copied into a test play, the same run fails on the `dnf` task
> with the right message, and the 17 default packages pass on a
> deployed CentOS Stream 9 node (`rpm -V --noconfig` returns 0 where
> plain `rpm -V` returns 2 because of two modified configuration
> files, so both parts of the fix are needed together).
>
> Would you accept a backport of #1244 and #1306 to `18-stable`? I can
> open the pull request if the cherry-pick robot is not the preferred
> way.

---
title: Fact sheet E
description: "Fact sheet for host bootstrap and operational playbooks in 2025.1: bootstrap-servers, prechecks, destroy, migrate-container-engine, prune-images, CLI."
tags: [bootstrap-servers, prechecks, destroy, migrate-container-engine, mariadb-backup, mariadb-recovery, facts, docker, podman, serial, limit]
---

# Fact sheet E

Source: `kolla-ansible` at tag `2025.1-eom` (commit `7222f0f`) and `ansible-collection-kolla` at tag `2025.1-eom`
(commit `09189c7`), which provides the roles that `bootstrap-servers` runs (`ansible/kolla-host.yml:12-14`;
`requirements.yml:2-5` pins the collection to the git branch `stable/2025.1`). Kolla-Ansible paths starting with
`tools/`, `doc/`, `tests/`, `etc/`, `zuul.d/`, `kolla_ansible/` or `ansible/` are relative to the repo root;
`roles/...`, `group_vars/...` and `*.yml` playbooks are relative to `ansible/`. In §1–§3, `etc_hosts/…`,
`baremetal/…`, `packages/…`, `docker/…`, `podman/…`, `kolla_user/…`, `docker_sdk/…`, `podman_sdk/…` and
`apparmor_libvirt/…` are ansible-collection-kolla `roles/<role>/…`. Ansible behaviour claims cite **ansible-core
2.18.20** (as `lib/ansible/...`). 2025.1 accepts ansible-core 2.17 to 2.18 (`requirements.txt:13`,
`roles/prechecks/vars/main.yml:4-5`); only 2.18.20 is read here, so ansible-core 2.17 behaviour is NOT AVAILABLE.

Labels: **FACT** = [CODE], read directly from the sources (cited): kolla-ansible, ansible-collection-kolla, the kolla
image repository (cited as kolla `docker/...`) or ansible-core. **NOT AVAILABLE** = [NOT AVAILABLE], these sources do
not establish it, often because it depends on Docker, Podman, containerd, systemd, Galera or libvirt behaviour, or on a
module that lives in an Ansible collection outside the sources (`ufw`, `selinux`, `sysctl`, `authorized_key`,
`git_config`, `docker_prune` are redirected out of ansible-core: ansible-core 2.18.20
`lib/ansible/config/ansible_builtin_runtime.yml`, e.g. `:745-746` for `docker_prune`). NOT AVAILABLE points are left
for the community to confirm (see [Lab tests](#lab-tests)).

> [!NOTE]
> **Key answers**
>
> - **Changed in 2025.1, Docker restart timing:** Docker still restarts only when the `daemon.json` write or the
>   registry CA copy reports changed, but a `meta: flush_handlers` now follows the daemon.json write directly
>   (`docker/tasks/config.yml:9-55`), so the restart happens **before** the drop-in and CA tasks, on every notified host
>   of the batch at once ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)).
> - **New in 2025.1, containerd and `docker system info`:** the role now runs `docker system info -f json` with no
>   `failed_when` (`config.yml:57-63`) and, on hosts whose Docker uses the containerd image store, rewrites
>   `/etc/containerd/config.toml` and restarts containerd (`config.yml:69-87`)
>   ([§2.3](#23-the-debianubuntu-mask-window)).
> - **New in 2025.1, `migrate-container-engine`:** stops every container on every baremetal host in one play, with no
>   confirmation, then redeploys ([§6.1](#61-migrate-container-engine-new-in-20251)).
> - **Changed in 2025.1, CLI:** the Bash wrapper is replaced by a Python CLI. `upgrade` and `reconfigure` always run
>   with `kolla_serial=0`, and a user `-e kolla_serial` can no longer change that; the three 2024.1 CLI bugs are gone;
>   without `-i` the CLI now passes `<configdir>/ansible/inventory/all-in-one` ([§11](#11-kolla-ansible-cli)).
> - **Changed in 2025.1, facts and destroy:** `--limit` fact gathering is still serial per limited host, but the new
>   `kolla_ansible_delegate_facts_hosts` can shrink it ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model));
>   `destroy` now protects `/etc/kolla` entries by Ansible's absolute `ansible_inventory_sources`
>   ([§6](#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)).
> - **Still holds in 2025.1:** `/etc/hosts` lists every baremetal host and one fact-less host fails the task on every
>   host ([§3](#3-etchosts-generation)); the systemd drop-in is never applied by a restart; Docker is masked on
>   Debian/Ubuntu during a run; no `kolla` user by default.

---

## 0. Most important findings

1. **When Docker restarts.** The restart is still the **handler** "Restart docker" (`docker/handlers/main.yml:10-15`:
   `state: restarted`, or `reloaded` when `docker_systemd_reload` is true, default `false`,
   `docker/defaults/main.yml:71`; plus `masked: false`). Only two tasks notify it: the `/etc/docker/daemon.json` write
   (`docker/tasks/config.yml:9-53`) and the private-registry CA copy (`:138-148`, only when `docker_registry_ca` is
   set). The systemd drop-in tasks notify "Reload docker service file" (`docker/handlers/main.yml:2-8`), a
   `daemon_reload`-only systemd call that **never reports changed** (ansible-core 2.18.20
   `lib/ansible/modules/systemd.py:390-403`; `changed` is set only at `:487,539,571`), and a handler notifies further
   handlers only when it reports changed (`lib/ansible/plugins/strategy/__init__.py:648`). **So Docker restarts if
   and only if the daemon.json write (or the CA copy) reports changed: the rendered content differs, or the file mode
   is not `0644`** (ansible-core 2.18.20 `lib/ansible/plugins/action/copy.py:283,344-383`,
   `lib/ansible/module_utils/basic.py:808,841,723`). **Changed in 2025.1:** the handlers are flushed right after the
   daemon.json write (`docker/tasks/config.yml:55`) and again at `:150-151`, on every notified host of the batch at
   once. The batch is all hosts by default: `kolla_serial` defaults to `0` (`kolla-host.yml:6`) and the CLI does not
   set it for `bootstrap-servers` ([§11](#11-kolla-ansible-cli)). Default content: `iptables: false`, `bridge: none`,
   `ip-forward: false` (`docker_disable_default_iptables_rules: "yes"`, `group_vars/all.yml:117-119`) and, on EL9
   hosts only, `default-ulimits` nofile (`docker/defaults/main.yml:51-54`). **Changed in 2025.1:**
   `docker_custom_config` is `{}` on every distribution (the openEuler `exec-opts` default is gone).
   Because of the new early flush, a host that fails in the drop-in or CA tasks (`config.yml:89-148`) has already
   restarted Docker for a daemon.json change; only a CA change can still be lost that way. The role has no
   `force_handlers` (grep of ansible-collection-kolla `roles/` is empty), the default is `False` (ansible-core 2.18.20
   `lib/ansible/config/base.yml:686-688`), and a failed host leaves the play
   (`lib/ansible/executor/play_iterator.py:504-515`) ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)).
2. **The systemd drop-in is never applied.** Still holds in 2025.1. The drop-in
   `/etc/systemd/system/docker.service.d/kolla.conf` carries `docker_http_proxy`/`docker_https_proxy`/`docker_no_proxy`
   and, on Zun compute hosts, `docker_zun_options` (`docker/templates/docker_systemd_service.j2`). Adding, changing
   or removing it does **not** restart Docker: it notifies only the reload handler, which never notifies the restart
   ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart); `docker/tasks/config.yml:89-126`). When dockerd picks the
   new settings up is NOT AVAILABLE (systemd behaviour).
3. **Docker is masked on Debian/Ubuntu during a run.** Still holds in 2025.1 for the Docker engine.
   `docker/tasks/install.yml:18-33` symlinks `/etc/systemd/system/docker.service -> /dev/null` whenever that path does
   not exist at that point. The unit is unmasked by "Start and enable docker" (`docker/tasks/config.yml:153-159`), by
   the "Restart docker" handler when it runs (`docker/handlers/main.yml:14`, now at the early flush when daemon.json
   changed), and by the recovery block `docker/tasks/install.yml:47-75` (after a package change with containers
   running). Whether that unmask removes the path again is NOT AVAILABLE (systemd behaviour). If the run fails or is
   interrupted in between, **the unmask does not run** ([§2.3](#23-the-debianubuntu-mask-window)). **New in
   2025.1:** the window now contains `docker system info` (`config.yml:57-63`), which has no `failed_when`; whether it
   fails on a host where Docker is stopped is NOT AVAILABLE (H19). NOT AVAILABLE: whether docker then starts at the
   next reboot. The `podman` role has no such step.
4. **New in 2025.1, a containerd restart.** When `docker system info` reports the `overlayfs` driver with the
   containerd snapshotter, the role renders `/etc/containerd/config.toml` and notifies "Restart containerd"
   (`docker/tasks/config.yml:65-87`, `docker/handlers/main.yml:17-21`), which runs at the flush at `:150-151`. Which
   hosts use that store, and what a containerd restart does to running containers, is NOT AVAILABLE (H20).
5. **`/etc/hosts` lists every host.** Still holds in 2025.1. The block loops over **all `groups['baremetal']` hosts**
   (`etc_hosts/tasks/etc-hosts.yml:25-41`), and it is the **first** thing the role does
   (`baremetal/tasks/main.yml:2-3`). So: (a) adding one host changes `/etc/hosts` on every host that bootstrap-servers
   runs on; (b) a baremetal host outside `bifrost` without gathered or cached facts makes `kolla_address` raise on
   **every** host (`kolla_ansible/kolla_address.py:107-114`), which ends the play for them before any other bootstrap
   task ([§3](#3-etchosts-generation)); (c) the per-run template work is O(N) per host, O(N²) in total.
6. **Fact gathering with `--limit` is serial per limited host.** Still holds in 2025.1. With `--limit` covering L of
   N hosts, each limited host loops over about N/L other hosts **in sequence** (`gather-facts.yml:34-62`;
   ansible-core 2.18.20 `lib/ansible/executor/task_executor.py:299,347`). **New in 2025.1:** N is now the length of
   `kolla_ansible_delegate_facts_hosts` (`gather-facts.yml:47`, default `groups['all']`, `group_vars/all.yml:43`),
   which the tuning guide documents narrowing (`doc/source/user/ansible-tuning.rst:164-203`). Fact caching still
   avoids the delegated calls (`ansible-tuning.rst:36-85`) ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)).
7. **Re-running `bootstrap-servers` changes the host.** Still holds in 2025.1. It disables ufw/firewalld
   (`baremetal/tasks/install.yml:3-32`, default `disable_firewall: true`, `baremetal/defaults/main.yml:30`), sets
   SELinux permissive (`baremetal/tasks/post-install.yml:21-28`, `baremetal/defaults/main.yml:25-27`), disables the
   libvirtd AppArmor profile on Ubuntu once (`apparmor_libvirt/tasks/remove-profile.yml:2-22`), **removes host
   packages** (`packages/tasks/main.yml:14-22`, `packages/defaults/main.yml:22-31`): on Debian/Ubuntu `lxd`, `lxc`,
   `open-iscsi` and, with the libvirt container (default for kvm/qemu, `group_vars/all.yml:945`), `libvirt-bin`; on
   RedHat, with the libvirt container, `libvirt`, `libvirt-daemon`, `iscsi-initiator-utils`. With Docker on
   Debian/Ubuntu it re-downloads the Docker apt key (`force: true`) and refreshes the apt cache on every run
   (`docker/tasks/repo-Debian.yml:26-33,68-71`; `cache_valid_time` defaults to 0, ansible-core 2.18.20
   `lib/ansible/modules/apt.py:1216,1383-1386`). **New in 2025.1:** the Docker SDK requirement is `docker>=7.0.0`
   (`docker_sdk/defaults/main.yml:35-40`). None of this restarts containers, but it is not a no-op on a hardened host.
8. **`kolla_serial` cannot batch `upgrade` or `reconfigure`.** **Changed in 2025.1.** `ANSIBLE_SERIAL` is a constant
   `0` in the Python CLI (`kolla_ansible/cli/commands.py:22`), passed as `kolla_serial` only by `reconfigure` (`:136`)
   and `upgrade` (`:278`), after the user's `-e`, so the CLI's `0` wins and there is no environment variable to
   change it ([§11](#11-kolla-ansible-cli), [F19](../findings.md#f19)). For `bootstrap-servers`, `deploy`,
   `prune-images` and the others, `-e kolla_serial=...` works (`bootstrap-servers.rst:83`).
9. **No `ansible.cfg` is shipped for users.** Still holds in 2025.1. The only ones are the CI template
   `tests/templates/ansible.cfg.j2` and a vagrant script. The tuning doc recommends pipelining, `forks`, `gathering =
   smart` with jsonfile fact caching, `inject_facts_as_vars = False`, a setup filter and gather subset,
   `kolla_max_fail_percentage` and, new in 2025.1, delegated fact gathering. **It says nothing about ControlPersist,
   mitogen, strategy or `serial` for scale** ([§12](#12-ansible-configuration-and-documented-tuning)).
10. **`destroy` acts on `hosts: all`, including the deploy host** (`localhost` is in `[deployment]`,
    `ansible/inventory/multinode:32-33`). `tools/cleanup-host` deletes **every** network namespace and every link
    whose line matches `tap`, `brq` or `vxlan`, and `rm -rf`s `/etc/kolla/*` except six names and the entries whose
    path equals one of `ansible_inventory_sources` (`tools/cleanup-host:5-23,72-97`; **changed in 2025.1**,
    `cleanup_host.yml:16`). `prune-images` is unchanged; whether it removes only dangling images is NOT AVAILABLE
    ([§7](#7-prune-images-ansibleprune-imagesyml-role-prune-images)).
11. **No `kolla` user by default.** Still holds in 2025.1. `create_kolla_user` defaults to `false` in
    ansible-collection-kolla (`baremetal/defaults/main.yml:20`, `docker_sdk/defaults/main.yml:54`,
    `podman_sdk/defaults/main.yml:47`) and kolla-ansible does not override it (grep of `ansible/` is empty). So by
    default bootstrap-servers creates no `kolla` user, group, authorized key or sudoers file
    (`baremetal/tasks/post-install.yml:2-4`), and `/etc/kolla` is not chowned (`:9-16`). The kolla-ansible doc still
    says the opposite ("which is ``true`` by default",
    `doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:107-108`).

---

## 1. `ansible/kolla-host.yml` (the `bootstrap-servers` command)

```yaml
# ansible/kolla-host.yml:1-14
- import_playbook: gather-facts.yml
- name: Apply role baremetal
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  max_fail_percentage: "{{ baremetal_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}"
  roles:
    - { role: openstack.kolla.baremetal, tags: baremetal }
```

- FACT: the CLI maps `bootstrap-servers` to `kolla-host.yml` with `-e kolla_action=bootstrap-servers` and
  `ansible_python_interpreter=auto_silent`, which a user `-e ansible_python_interpreter=...` replaces
  (`kolla_ansible/cli/commands.py:67-77,158-170`). The role is `openstack.kolla.baremetal` from
  ansible-collection-kolla, installed by `kolla-ansible install-deps` from the git branch named in
  `requirements.yml:2-5`. **Changed in 2025.1:** `install-deps` now always installs `requirements-core.yml` as well
  (pinned galaxy collections, among them `community.docker <5` and `containers.podman <2`,
  `requirements-core.yml:18-23`; `kolla_ansible/ansible.py:307-318`); in 2024.1 it did so only when the `ansible` pip
  package was absent. This sheet reads the `2025.1-eom` tag; what a later install of that branch contains is NOT
  AVAILABLE.
- FACT: `max_fail_percentage` (`kolla-host.yml:8-11`). With the default 100 it never stops the play
  early: the check counts the failures of the current batch only (ansible-core 2.18.20
  `lib/ansible/executor/playbook_executor.py:182-188`, `lib/ansible/executor/task_queue_manager.py:326-334`).
- FACT: the role does not dispatch on `kolla_action`. `baremetal/tasks/main.yml:1-15` runs, in order: the `etc_hosts`
  role, `pre-install.yml`, `install.yml` (which imports the `packages` role and **the engine role**
  `openstack.kolla.{{ container_engine }}`, `baremetal/tasks/install.yml:34-38`), `post-install.yml` (which imports
  `kolla_user`, `openstack.kolla.{{ container_engine }}_sdk` and `apparmor_libvirt`), then optionally
  `configure-ceph-for-zun.yml` (`zun_configure_for_cinder_ceph` and host in `zun-compute`).
- FACT: `container_engine` is `{{ kolla_container_engine | default('docker') }}`
  (`baremetal/defaults/main.yml:37`), and kolla-ansible sets `kolla_container_engine: "docker"`
  (`group_vars/all.yml:100`; the only other documented value is `podman`, `etc/kolla/globals.yml:91-92`). So the
  default still installs Docker and the Docker SDK; `podman` selects the `podman` and `podman_sdk` roles. **Changed
  in 2025.1:** each engine and SDK role now runs `{{ package_action }}.yml`, `install` by default
  (`docker/tasks/main.yml:2`, `docker/defaults/main.yml:84`; the same in `podman`, `docker_sdk` and `podman_sdk`),
  and gains an `uninstall.yml` that only the new `migrate-container-engine` command uses
  ([§6.1](#61-migrate-container-engine-new-in-20251)).
- FACT: the target is `hosts: baremetal`, which in the sample inventories is control, network, compute, storage and
  monitoring
  (`ansible/inventory/multinode:35-40`). The deploy host (`[deployment]`) is **not** bootstrapped.
- FACT: there are no task-level tags inside the collection roles (grep of `tags:` in ansible-collection-kolla `roles/`
  is
  empty). `--tags` can only select `baremetal` plus the `always`-tagged gather-facts plays (`gather-facts.yml:26,62`).
  A subset of bootstrap tasks cannot be chosen with tags.
- FACT: the default `serial` is `"0"`, meaning one batch of all hosts. Parallelism is limited only by Ansible's
  `forks` setting: the 2025.1 CLI no longer has a `--forks` option
  ([Repository architecture §2](../../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook)).
- CI coverage: `bootstrap-servers` runs on fresh hosts (`tests/setup_gate.sh:39`) and, **new in 2025.1**, a second
  time in the upgrade jobs, on the deployed 2024.1 cloud before the upgrade (`tests/upgrade.sh:16-20`, whose comment
  says the run brings the Python libraries to the new versions). CI has Podman jobs (`zuul.d/jobs.yaml:32-39,52-58`).
  The re-run hazards below are read from the code; runtime effects that the code does not show are marked NOT
  AVAILABLE.

### 1.1 Task-by-task: `pre-install.yml`

As in 2024.1, `baremetal/tasks/pre-install.yml` holds a single task; the `/etc/hosts` work is in the `etc_hosts` role,
which runs just before it, and the engine repository tasks are in the `docker` role, which runs during the install
phase ([§1.2](#12-task-by-task-installyml)).

| Lines | Task | Change made | Scale | Safe to re-run on a prod host with VMs? |
|---|---|---|---|---|
| `etc_hosts/tasks/etc-hosts.yml:2-10` | Ensure `127.0.0.1 localhost` (lineinfile, regexp `^127.0.0.1.*`, `create: true`, mode `0644`) | Replaces the **last** `127.0.0.1` line with exactly `127.0.0.1 localhost` | per host, O(1) | Yes. It may strip extra aliases from a hand-edited 127.0.0.1 line. |
| `etc-hosts.yml:18-23` | Remove `127.0.1.1 ... <hostname>` line | Deletes the Ubuntu-style hostname→127.0.1.1 mapping (RabbitMQ bug refs in comment, lines 12-17) | per host | Yes |
| `etc-hosts.yml:25-41` | **Generate /etc/hosts for all of the nodes** (blockinfile `# {mark} ANSIBLE GENERATED HOSTS`) | One line per **every host in `groups['baremetal']`**: `<api addr> <nodename> <hostname>` | **O(N) lines per host, O(N²) Jinja/hostvars work in total**. Needs facts of all N hosts. | Yes (no restart is attached). But see [§3](#3-etchosts-generation). |
| `etc-hosts.yml:47-60` | If `/etc/cloud/cloud.cfg` exists, write `/etc/cloud/cloud.cfg.d/99-kolla.cfg` = `manage_etc_hosts: false` (mode `0660`) | Stops cloud-init from rewriting /etc/hosts at boot | per host | Yes |
| `baremetal/tasks/pre-install.yml:2-9` | `net.ipv4.ping_group_range=0 2147483647` (RedHat only) into `kolla_sysctl_conf_path` (`/etc/sysctl.conf`, `group_vars/all.yml:819`) | `sysctl` is `ansible.posix.sysctl`: whether it reloads sysctl, and when, is NOT AVAILABLE | per host | Yes |

All four `etc_hosts` tasks run only when `customize_etc_hosts` (default `true`, `etc_hosts/defaults/main.yml:3`;
`etc_hosts/tasks/main.yml:2-4`). The `sudo` and `kolla` groups are created by the `kolla_user` role, which runs only
when `create_kolla_user` is true (default `false`, [§1.3](#13-task-by-task-post-installyml)).

### 1.2 Task-by-task: `install.yml`

Rows marked *Docker* run only with `kolla_container_engine: docker` (the default); rows marked *Podman* only with
`podman` (`baremetal/tasks/install.yml:37-38`).

| Lines | Task | Notes, scale, re-run safety |
|---|---|---|
| `baremetal/tasks/install.yml:3-32` | **Firewall** (`when: disable_firewall`, default `true`, `baremetal/defaults/main.yml:30`): `ufw state=disabled policy=allow` (Debian, `ignore_errors`), `rpm -q firewalld`, then **stop and disable firewalld** (RedHat) | **Silently removes any host firewall an operator added since the last run.** Per host. Containers are not restarted. (`ufw` is `community.general.ufw`; its exact effect is NOT AVAILABLE.) |
| `packages/tasks/main.yml:2-12` | Install `ubuntu_pkg_install` (Debian family: `git`, `iputils-ping`, `sg3-utils-udev` if `enable_multipathd`, `tzdata`), or `redhat_pkg_install` (`git`, `iputils`, `sudo` and, **new in 2025.1**, `kernel-modules-extra-matched` on major version 10) (`packages/defaults/main.yml:10-20`), `state: present`. **Changed in 2025.1:** the openEuler list is gone | On Debian the apt cache is refreshed only when it is older than `apt_cache_valid_time`, 3600 s (`packages/defaults/main.yml:3`; ansible-core 2.18.20 `lib/ansible/modules/apt.py:1383-1386`). |
| `packages/tasks/main.yml:14-22` | **Remove packages** (`state: absent`): Debian family `lxd`, `lxc`, `open-iscsi`, plus `libvirt-bin` if `enable_nova_libvirt_container`; RedHat `libvirt`, `libvirt-daemon`, `iscsi-initiator-utils`, only if `enable_nova_libvirt_container` (`packages/defaults/main.yml:22-31`) | `enable_nova_libvirt_container` is true for `nova_compute_virt_type` kvm or qemu (`group_vars/all.yml:945`; default `kvm`, `:1253`). **A host that uses host-level iSCSI (for example boot-from-SAN, or a storage agent) loses `open-iscsi` (always on Debian/Ubuntu) or `iscsi-initiator-utils` (RedHat, with the libvirt container).** Re-running is a no-op only if the packages are already gone. Same with both engines. |
| *Docker* `docker/tasks/install.yml:2-3` → `repo-Debian.yml:2-71` | **Changed in 2025.1:** the repository tasks are now included from `install.yml`, and `enable_docker_repo` is plainly `true` (`docker/defaults/main.yml:6`; the openEuler exception is gone). `ca-certificates`, `gnupg` `state: present` (2-10); `/etc/apt/sources.list.d`, `/etc/apt/keyrings` (12-24); **Docker apt key downloaded with `force: true`** (26-33), with the environment from `docker_apt_key_env`, **new in 2025.1** (`:33`; default `{}`, `docker/defaults/main.yml:18`, for example a proxy); optional apt pin from `docker_apt_package_pin` (35-44). The old `/etc/apt/sources.list.d/docker.list` is deleted (46-50), the repository is written as the deb822 file `/etc/apt/sources.list.d/docker.sources` with `Signed-by: /etc/apt/keyrings/docker.asc` (54-66), then the apt cache is refreshed (68-71) | Needs network access to the Docker repository and to the apt mirrors on every run: the key is fetched each time, and the cache refresh at 68-71 passes no `cache_valid_time` (default 0, ansible-core 2.18.20 `lib/ansible/modules/apt.py:1216,1383-1386`). |
| *Docker* `docker/tasks/repo-RedHat.yml:2-27` | yum repo `docker` with `module_hotfixes: true` (9-20), rpm_key (22-27) | Repo config |
| *Docker* `docker/tasks/install.yml:8-14` | `docker ps -f status=running -q` → `running_containers` | Snapshot taken before package changes |
| *Docker* `docker/tasks/install.yml:19-22` | stat `/etc/systemd/system/docker.service` | `stat` does not follow symlinks by default (`follow` defaults to False, ansible-core 2.18.20 `lib/ansible/modules/stat.py:448,461,469`) |
| *Docker* **`docker/tasks/install.yml:24-32`** | **Mask docker (symlink to /dev/null) on Debian/Ubuntu when that file does not exist** | Intended to stop apt from auto-starting docker before daemon.json exists (comment 16-17). It also fires on any re-run where the path is absent. Whether the unmask removes the symlink, so that **every re-run** masks again, is NOT AVAILABLE. See [§2.3](#23-the-debianubuntu-mask-window). |
| *Docker* `docker/tasks/install.yml:35-42` | Install `docker_packages` with **`state: present`**, `update_cache: true` (apt with `cache_valid_time` 3600) | **An already-installed `docker-ce` is NOT upgraded** (`present`, not `latest`). List (`docker/defaults/main.yml:29-32`): `docker-ce` (or `docker-ce-<docker_yum_package_pin>` on RedHat, `:25`), `apparmor` on Debian, `iptables` only if `not docker_disable_default_iptables_rules` (default `"yes"`, so not installed). Whether a changed pin up- or downgrades an installed engine is NOT AVAILABLE (package manager behaviour). Doc: `bootstrap-servers.rst:64-67,90-93`. |
| *Docker* `docker/tasks/install.yml:47-75` | If the install result changed **and** containers were running: `systemd docker started/enabled/unmasked`, wait for `docker info` (6×10 s), then `docker start <previously running IDs>` | Recovery path after a package change (comment at 5-6: an engine upgrade "may cause containers to stop"). What `docker start` does to containers that are still running is NOT AVAILABLE. |
| *Docker* `docker/tasks/config.yml:1-159` (imported at `install.yml:77`) | `/etc/docker`, **daemon.json** (notifies "Restart docker", 9-53), **new in 2025.1: a handler flush right after it** (55), `docker system info -f json` (57-63) to decide whether Docker uses the containerd image store (65-75), then `/etc/containerd/config.toml` in that case (notifies "Restart containerd", 77-87), drop-in removal or template (notify "Reload docker service file", 89-126), registry CA (notifies "Restart docker", 128-148), **flush handlers** (150-151), start and enable docker (`masked: false`, 153-159) | See [§2](#2-docker-daemon-configuration-and-restart-the-exact-trigger). |
| *Docker* `docker/tasks/install.yml:79-82` | Zun containerd config (only `containerd_configure_for_zun` and host in `zun-cni-daemon`) | See below |
| *Podman* `podman/tasks/install.yml:4-10` | `podman ps -f status=running -q` → `running_containers` | Snapshot taken before package changes |
| *Podman* `podman/tasks/install.yml:12-19` | Install `podman_packages` (`podman`, plus `catatonit` on Debian, `podman/defaults/main.yml:6-8`), `state: present`, `update_cache: true` | An installed `podman` is not upgraded (`present`). No repository task: the distribution packages are used (the role has no repo file; `podman/tasks/main.yml:2` only includes `{{ package_action }}.yml`). |
| *Podman* `podman/tasks/install.yml:24-29` | `podman.socket` `state: started`, `enabled: true` | Every run. kolla-ansible's Podman worker talks to `/run/podman/podman.sock` (`ansible/module_utils/kolla_podman_worker.py:21`). |
| *Podman* `podman/tasks/install.yml:31-48` | If the install result changed **and** containers were running: wait for `podman info` (6×10 s), then `podman start <previously running IDs>` | Same recovery pattern as Docker. What `podman start` does to running containers is NOT AVAILABLE. |
| *Podman* `podman/tasks/config.yml:2-77` | `/etc/containers/{containers,registries,storage}.conf.d` (2-11); registry, mirror and storage drop-ins only when `podman_registry`, `podman_registry_mirror`, `podman_storage_driver` or `podman_runtime_directory` is set (13-53); CA path and copy (55-77); imported at the end of `install.yml` (`podman/tasks/install.yml:50`) | All four variables default to empty (`podman/defaults/main.yml:11-23`) and kolla-ansible sets none of them (grep of `ansible/` and `etc/` is empty), so by default only the directories are created. **`docker_registry` does not reach Podman's registry config.** The CA copy task (67-77) reads `private_registry_ca` and `private_registry`, which neither the collection nor kolla-ansible defines (grep); it therefore cannot render unless the operator defines them. No task notifies anything: the role has no handlers. |

### 1.3 Task-by-task: `post-install.yml`

| Lines | Task | Notes |
|---|---|---|
| `baremetal/tasks/post-install.yml:2-4` → `kolla_user/tasks/main.yml:2-10` | groups `docker`, `sudo`, `kolla_group` | Only when `create_kolla_user`, **default `false`** (`baremetal/defaults/main.yml:20`; not overridden in kolla-ansible). The `docker` group is created with either engine. |
| `kolla_user/tasks/main.yml:12-21` | user `kolla` (group `kolla`, `groups: [docker, sudo]`, append) | Same condition |
| `kolla_user/tasks/main.yml:23-27` | `authorized_key` from `kolla_ssh_key.public_key` (passwords.yml) | Same condition. `authorized_key` is `ansible.posix.authorized_key`; whether an old key is removed when the key in passwords.yml is rotated is NOT AVAILABLE (no `exclusive` or `state` is passed) |
| `kolla_user/tasks/main.yml:29-38` | `/etc/sudoers.d/kolla-ansible-users`: `kolla ALL=(ALL) NOPASSWD: ALL`, mode `0640` | Same condition plus `create_kolla_user_sudoers` (default true, `kolla_user/defaults/main.yml:2`) |
| *Docker* `post-install.yml:6-7` → `docker_sdk/tasks/main.yml:1-22` → `docker_sdk/tasks/install.yml:1-101` | On Python ≥ 3.10, a `stat` of `<stdlib>/EXTERNALLY-MANAGED` sets `docker_sdk_python_externally_managed` (`main.yml:2-20`), then `{{ package_action }}.yml` (`:22`). **New in 2025.1**, on **Debian** with an externally managed Python and no virtualenv: an osbpo apt key and the repository `bookworm-bobcat-backports-nochange` through `apt_repository` with `filename: osbpo` (`install.yml:2-33`; `docker_sdk/defaults/main.yml:63-64`). Packages `python3-setuptools`, `python3-pip`, and `python3-docker` plus `python3-dbus` when the Python is externally managed and no virtualenv is used; otherwise the dbus build dependencies (`dbus-glib-devel` and `dbus-x11` now only on major version 9) (`docker_sdk/defaults/main.yml:3-31`; task `install.yml:35-41`). With an existing virtualenv directory, `packaging` is pip-installed into it first (43-76), then `pip>19.3` and `packaging` (78-89). **Docker SDK, changed in 2025.1:** `docker>=7.0.0`, `requests` with no upper bound, and `dbus-python`, via the `pip` next to the host Python or into the venv (`docker_sdk/defaults/main.yml:35-40`; task 91-101) | The pip step is skipped when the Python is externally managed and no virtualenv is used (`:101`). `state` defaults to present, so no change if matching versions are installed; whether an installed `docker` 6.x SDK is upgraded to satisfy `>=7.0.0` is NOT AVAILABLE (`pip` module behaviour, outside the sources read). Needs PyPI if not installed. Per host. |
| *Podman* `post-install.yml:6-7` → `podman_sdk/tasks/main.yml:1-22` → `podman_sdk/tasks/install.yml:1-117` | Same externally-managed check; on **Debian** with an externally managed Python and no virtualenv, an osbpo apt key (template), removal of `osbpo.list`, a deb822 repository `bookworm-bobcat-backports-nochange` written to **`/etc/apt/sources.list.d/docker.sources`**, and a cache refresh (`install.yml:2-49`); packages `python3-setuptools`, `python3-pip`, and `python3-podman` plus `python3-dbus` in the same case (`podman_sdk/defaults/main.yml:3-7`; task 51-57); pip `podman>=4.7.0` and `dbus-python` otherwise (`podman_sdk/defaults/main.yml:11-15`; task 107-117) | The osbpo repository file still has the same path as the Docker role's repository file (`docker/tasks/repo-Debian.yml:56`), so on a Debian host that ran the Docker role before, it replaces the Docker repository definition. **Changed in 2025.1:** the virtualenv tasks now use `podman_sdk_virtualenv_owner`, defined in the role (`podman_sdk/defaults/main.yml:51`), which settles the 2024.1 question about `docker_sdk_virtualenv_owner`. |
| `post-install.yml:9-16` | `node_config_directory` (`/etc/kolla`), mode `0755`, owned by `kolla:kolla` only when `create_kolla_user` | |
| `post-install.yml:18-19` → `apparmor_libvirt/tasks/remove-profile.yml:2-22` | Ubuntu only, when `apparmor_remove_libvirt_profile` (= `enable_nova_libvirt_container`, `apparmor_libvirt/defaults/main.yml:6`; true by default through `group_vars/all.yml:945`): if `/etc/apparmor.d/usr.sbin.libvirtd` exists and `/etc/apparmor.d/disable/usr.sbin.libvirtd` does not, `apparmor_parser -v -R` the profile **and** link it into `disable/` | `changed_when: true`. The disable link makes the task skip on later runs, so it runs once per host. |
| `post-install.yml:21-28` | `selinux: policy=targeted state={{ selinux_state }}` (default `permissive`, `change_selinux: true`, `baremetal/defaults/main.yml:25-27`) on RedHat | `selinux` is `ansible.posix.selinux`: whether it also changes the running mode is NOT AVAILABLE. No reboot is done by the role. |
| `post-install.yml:30-42` | global git `https.proxy` / `http.proxy` from `git_https_proxy` / `git_http_proxy` (default empty) | `community.general.git_config` |
| `baremetal/tasks/main.yml:11-15` → `configure-ceph-for-zun.yml:2-81` | Ceph repository, EPEL on RedHat, `ceph-common` (only `zun_configure_for_cinder_ceph` and host in `zun-compute`). On Debian the key is downloaded to `/etc/apt/keyrings/ceph.gpg` with `force: true`, `ceph.list` is removed and a deb822 `ceph.sources` is written (`:5-43`) | Needs network access to `download.ceph.com` |

There are still no `enable_host_ntp` tasks: no collection role names `ntp` (grep). Time sync is only checked, by
`prechecks` ([§5](#5-ansiblerolesprechecks-kolla-ansible-prechecks)).

`configure-containerd-for-zun.yml` (Docker only; only `containerd_configure_for_zun` **and** host in `zun-cni-daemon`,
`docker/tasks/install.yml:79-82`): it writes the CNI config and script and **overwrites `/etc/containerd/config.toml`**
with `[grpc] gid = ...` (`docker/templates/containerd_config.toml.j2:1-3`). The CNI config and `config.toml` templates
notify **"Restart containerd"** (`configure-containerd-for-zun.yml:11-20,38-45`; `docker/handlers/main.yml:17-21`).
These tasks come after the last explicit flush in `config.yml`, so the containerd restart runs at the play's implicit
flush after all roles, that is after post-install (ansible-core 2.18.20 `lib/ansible/playbook/play.py:327-333`).
**New in 2025.1**, a second path writes the same file on hosts that are not Zun hosts: when `docker system info`
reports the `overlayfs` driver with the containerd snapshotter, `config.yml:77-87` renders
`disabled_plugins = ["cri"]` and `root = "/var/lib/docker/containerd"` (`containerd_config.toml.j2:4-9`,
`docker/defaults/main.yml:9`) and notifies "Restart containerd", which then runs at the flush at `config.yml:150-151`.
NOT AVAILABLE: which hosts Docker sets up with the containerd image store, and whether container shims survive a
containerd restart.

Kernel modules: the bootstrap roles load **none** (grep for `modprobe`/`module-load` in ansible-collection-kolla
`roles/`
is empty). Modules and sysctls are applied during `deploy`/`reconfigure` by `config-host.yml` in service roles: the
`module-load` role from `ironic`, `iscsi`, `loadbalancer`, `multipathd`, `neutron`, `nova-cell` and `openvswitch`, and
sysctls from `loadbalancer` and `neutron` (through the `sysctl` role, e.g.
`roles/neutron/tasks/config-host.yml:20-22`),
`nova-cell` and `opensearch` (grep of `roles/*/tasks/config-host.yml`).

---

## 2. Docker daemon configuration and restart: the exact trigger

This section applies to `kolla_container_engine: docker`, the default. For Podman see
[§2.5](#25-with-kolla_container_engine-podman).

### 2.1 What goes into `/etc/docker/daemon.json`

Base dict (`docker/vars/main.yml:2-5`): `log-opts: {max-file: docker_log_max_file, max-size: docker_log_max_size}`
(defaults `"5"` / `"50m"`, `group_vars/all.yml:122-123`). Keys merged in by `docker/tasks/config.yml:9-47`:

| Key | Source / condition | Default | Line (`config.yml`) |
|---|---|---|---|
| `docker_zun_config` (Zun) | `docker_configure_for_zun` **and** host in `zun-compute` | off (`all.yml:132`); `docker_zun_config: {}` (`all.yml:134`), so nothing is added | 37 |
| `insecure-registries: [docker_registry]` | `docker_registry_insecure` true | `"no"` (`all.yml:111`); `docker_registry: "quay.io"` (`all.yml:106`) | 12-14, 38 |
| `registry-mirrors` | `docker_registry_mirrors` non-empty | `[]` (`docker/defaults/main.yml:64`) | 15-16, 39 |
| `storage-driver` | `docker_storage_driver` non-empty | `""` (`docker/defaults/main.yml:34`) | 17-18, 40 |
| `data-root` | `docker_runtime_directory` non-empty | `""` (`all.yml:112`) | 19-20, 41 |
| `iptables: false` | `docker_disable_default_iptables_rules` | **`"yes"`** (`all.yml:117`) | 21-22, 42 |
| `bridge: none` | `docker_disable_default_network` | follows the previous (`all.yml:118`) | 23-24, 43 |
| `ip-forward: false` | `docker_disable_ip_forward` | follows the previous (`all.yml:119`) | 25-26, 44 |
| `default-ulimits: {nofile: 1048576/1048576}` | `docker_ulimit_nofile` | true on RedHat-family major version 9 only, so not on 10 (`docker/defaults/main.yml:52-54`) | 27-32, 45 |
| `debug` | `docker_debug` | `false` (`docker/defaults/main.yml:74`) | 33-34, 46 |
| anything | `docker_custom_config` (dict) | `{}` on every distribution (`docker/defaults/main.yml:35`); **changed in 2025.1:** the openEuler default `{"exec-opts": ["native.umask=normal"]}` is gone | 47 |

FACT: the file is rendered with Ansible's `to_nice_json`, which uses `sort_keys=True`
(ansible-core 2.18.20 `lib/ansible/plugins/filter/core.py:77-81`), so key order is stable and does not cause spurious
changes.
FACT: `copy content:` **overwrites the whole file**. Any key added by hand (for example `"live-restore": true` added
outside `docker_custom_config`) is **removed**, and that removal itself triggers a restart.
FACT: when `docker_registry_ca` is set, the CA is copied to `/etc/docker/certs.d/<docker_registry>/ca.crt` and a change
also notifies "Restart docker" (`config.yml:128-148`).

### 2.2 Why `docker_reloaded` never triggers a restart

There is no `docker_reloaded` register in 2025.1; its successor is the "Reload docker service file" handler, and the
reason it never leads to a restart is the same.

```python
# ansible-core 2.18.20 lib/ansible/modules/systemd.py:390-403
result = dict(name=unit, changed=False, status=dict())
# Run daemon-reload first, if requested
if module.params['daemon_reload'] and not module.check_mode:
    (rc, out, err) = module.run_command("%s daemon-reload" % (systemctl))
    if rc != 0: ... module.fail_json(...)
```
`changed` is set to True only by the `masked`, `enabled` and `state` branches (lines 487/539/571). The handler
"Reload docker service file" (`docker/handlers/main.yml:2-8`) passes only `name` and `daemon_reload`, so it always
reports unchanged, and its `notify: Restart docker` never fires: notifications are processed only for changed results
(ansible-core 2.18.20 `lib/ansible/plugins/strategy/__init__.py:648`).

**Conclusion (FACT for ansible-core 2.18.20):** during `bootstrap-servers`, the Docker daemon restarts **only** when the
write of daemon.json, or of the registry CA file, reports changed (rendered content differs from the file on disk, or
its mode differs; `lib/ansible/plugins/action/copy.py:283,344-383`, `lib/ansible/module_utils/basic.py:808,841,723`).
**Changed in 2025.1:** a `meta: flush_handlers` now follows the daemon.json write directly (`docker/tasks/config.yml:55`),
so a daemon.json change restarts Docker **before** the drop-in and CA tasks run; a CA change restarts it at the second
flush (`:150-151`). Triggers:
- first bootstrap of a host (the file does not exist yet), or any hand-edited daemon.json;
- a host whose daemon.json was rendered with other defaults (for example `iptables`, `bridge`, `ip-forward`,
  `group_vars/all.yml:117-119`; `default-ulimits` on EL9);
- **new in 2025.1:** an EL10 host that carries a daemon.json with `default-ulimits` from an earlier run, which the
  2025.1 default no longer renders there (`docker/defaults/main.yml:52`); and an openEuler host, whose `exec-opts`
  default is gone (`:35`);
- changing `docker_registry_insecure` (and `docker_registry` while it is true), `docker_registry_mirrors`,
  `docker_debug`, `docker_log_max_file`, `docker_log_max_size`, `docker_storage_driver`, `docker_runtime_directory`,
  `docker_disable_default_iptables_rules`, `docker_disable_default_network`, `docker_disable_ip_forward`,
  `docker_ulimit_nofile*` or `docker_custom_config`;
- with `docker_registry_ca` set: a changed CA file, or a changed `docker_registry` (new destination path);
- a **package change** does not notify the handler by itself. What a docker-ce package upgrade does to the daemon
  is NOT AVAILABLE; the role's comment says it "may cause containers to stop" (`docker/tasks/install.yml:5-6`). Kolla
  then runs `docker start` on previously running containers (`docker/tasks/install.yml:47-75`). The kolla-ansible doc
  says a package update "will cause the Docker engine to restart" (`bootstrap-servers.rst:64-67`); the sources do not
  show the mechanism (package manager behaviour).

With `docker_systemd_reload: true` the handler reloads instead of restarting (`docker/handlers/main.yml:13`); which
daemon.json changes dockerd applies on a reload is NOT AVAILABLE (Docker behaviour).

**New in 2025.1, a containerd restart.** After the first flush the role reads `docker system info -f json`
(`config.yml:57-63`, `check_mode: false`) and, when Docker uses the containerd image store, renders
`/etc/containerd/config.toml` and notifies "Restart containerd" (`config.yml:69-87`, `docker/handlers/main.yml:17-21`),
which runs at the flush at `:150-151`. Whether Docker uses that store, and what a containerd restart does to running
containers, is NOT AVAILABLE (Docker and containerd behaviour).

**Not** triggers (latent changes): adding, changing or removing `docker_http_proxy`, `docker_https_proxy`,
`docker_no_proxy`, or the Zun `docker_zun_options` drop-in (`docker/tasks/config.yml:89-126`). These are written to disk
and daemon-reloaded, and no Kolla task restarts Docker for them. When dockerd picks them up is NOT AVAILABLE (systemd
behaviour). NOT AVAILABLE: whether dockerd refuses to start if the same option ends up both as a dockerd flag in the
drop-in and in daemon.json.

### 2.3 The Debian/Ubuntu mask window

Sequence per run on Debian/Ubuntu with Docker (FACT): `docker/tasks/install.yml:24-32` mask (the symlink is created
when `/etc/systemd/system/docker.service` is absent), then the Docker package install (`:35-42`) and the recovery
block (`:47-75`, which sets `masked: false`, but only when the package install changed and containers were running),
then daemon.json (`docker/tasks/config.yml:9-53`) and, **new in 2025.1**, the first flush (`:55`; "Restart docker"
carries `masked: false` when notified), then `docker system info` (`:57-63`), the containerd, drop-in and CA tasks
(`:69-148`), the second flush (`:150-151`), and finally `config.yml:153-159` `masked: false`, which runs
`systemctl unmask docker` when systemd reports the unit as masked (ansible-core 2.18.20
`lib/ansible/modules/systemd.py:480-499`). Pip installs, user creation and the AppArmor and SELinux tasks come after the
unmask (`baremetal/tasks/main.yml:7-9`).
FACT: a failure or interruption between the mask and the unmask, unless the recovery block or the "Restart docker"
handler has run, leaves the symlink in place. The roles have no `rescue` or `always` except the best-effort file
cleanup of the new `uninstall.yml` (grep of ansible-collection-kolla `roles/`), and a failed host runs no further task
of the play (ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:504-515`).
**New in 2025.1:** `docker system info` (`config.yml:57-63`) has no `failed_when`, so a non-zero exit fails the host
inside that window. Whether it exits non-zero when the daemon is not running is NOT AVAILABLE (Docker behaviour).
NOT AVAILABLE: whether the running daemon is affected, and whether **Docker, and therefore every Kolla container and VM
on that host, starts after the next reboot**. One related statement in the sources is the Ansible systemd
module's note that "a masked unit is impossible to start" (ansible-core 2.18.20 `lib/ansible/modules/systemd.py:47`).
Also NOT AVAILABLE: whether `systemctl unmask` removes the symlink, which decides whether the next run masks again.
Check after any failed run: `ls -l /etc/systemd/system/docker.service` should **not** point to `/dev/null`.

### 2.4 Blast radius of a restart

- FACT: the restart is the "Restart docker" handler, run at the flush at `docker/tasks/config.yml:55` (daemon.json) or
  `:150-151` (CA) on every notified host of the current batch. With default `serial: 0`, **all baremetal hosts whose
  daemon.json changed restart Docker in the same step** (subject to forks). That includes all controllers at once.
- FACT: in 2025.1 `kolla_container`'s Docker worker still gives containers no Docker restart policy (in
  `module_utils/kolla_docker_worker.py` `restart_policy` appears only in the one-shot checks at `:349,392,461`). Each
  container runs under a systemd unit `kolla-<name>-container.service` with `After=` and `Wants=docker.service` (for
  Docker; `network-online.target` otherwise), `ExecStart=/usr/bin/<engine> start -a <name>`,
  `ExecStop=/usr/bin/<engine> stop <name> -t <graceful_timeout>` and `Restart=always` for `unless-stopped`
  (`module_utils/kolla_systemd_worker.py:20-40,51-59`; `docker_restart_policy`, `group_vars/all.yml:126`). **Changed
  in 2025.1:** the unit also carries `PartOf=kolla.target` (`:27`), a target the `common` role installs
  (`roles/common/tasks/config.yml:54-58`), so the first 2025.1 check of a container whose unit 2024.1 wrote reports a
  difference ([F16](../findings.md#f16)). NOT AVAILABLE: whether those units bring the containers back after the daemon restarts
  (systemd and Docker behaviour). FACT: the Docker path sets no container `StopTimeout` (grep for
  `stop_timeout|StopTimeout` in `library/` and `module_utils/` finds only the Podman worker,
  `module_utils/kolla_podman_worker.py:60,126`). `docker_graceful_timeout: 60` (`all.yml:148`) is used by the unit's
  `ExecStop` and by the Docker worker's stops (`module_utils/kolla_docker_worker.py:426-441,450-470`), not by the
  daemon. NOT AVAILABLE: the stop timeout Docker applies to containers on a daemon restart.
- NOT AVAILABLE: whether restarting Docker on all MariaDB hosts at once stops the whole Galera cluster. FACT: the kolla
  image has no recovery logic for it. On a normal start the container runs `mysqld_safe` (plus `BOOTSTRAP_ARGS` only if
  set) with every MariaDB host of the shard in `gcomm://`, and the image's start path has no `grastate.dat` or
  `safe_to_bootstrap` handling and no new-cluster decision (kolla `docker/mariadb/mariadb-server/extend_start.sh:31-61`;
  `roles/mariadb/templates/galera.cnf.j2:33`;
  [Kolla images §5.4](../../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)). NOT AVAILABLE: whether
  Galera re-forms the cluster by itself or `kolla-ansible mariadb_recovery` is needed. With a single MariaDB host in the
  shard, `gcomm://` is empty (`galera.cnf.j2:33`); whether that host comes back without recovery is NOT AVAILABLE.
- Compute nodes: `nova_libvirt` runs with `pid_mode: host`, `cgroupns_mode: host` and bind-mounts `/sys/fs/cgroup`
  (`roles/nova-cell/defaults/main.yml:10-11,380-388`). NOT AVAILABLE: whether running QEMU processes survive the container
  restart; the sources do not show whether the guests sit in machined slices or in the container cgroup. Note
  `tools/cleanup-containers:16-22`: "Container engine ($engine) will not be able to stop the nova_libvirt container
  with those [qemu processes] running".
- **Optional unit hazard:** `tools/setup-compute-libvirt.yml` (not run by any kolla-ansible command) installs
  `kolla-libvirt-guests-<engine>.service` (`:9-11,13-17`). The docker variant has `Requires=docker.service`, and its
  `ExecStop` stops nova_compute and runs `libvirt-guests.sh shutdown`
  (`tools/kolla-libvirt-guests-docker.service:6,18-19`).
  NOT AVAILABLE: whether systemd propagates a restart of `docker.service` to units that `Requires=` it, and so whether,
  on hosts where an operator installed this unit, **a Docker restart shuts down or managed-saves every guest**.
- Documented mitigations (`doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:56-88`): `--limit`
  batches
  keeping quorum, `-e kolla_serial=30%`, or Docker `live-restore` ("issues reported ... use it at your own risk"). The
  way to
  set live-restore in a supported way is `docker_custom_config: {"live-restore": true}`. FACT: adding it changes the
  rendered daemon.json, so that run restarts Docker ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)); if the
  file on disk already matches the rendered content, the handler is not notified. NOT AVAILABLE: whether containers
  survive that first restart, and whether pre-seeding daemon.json by hand and running `systemctl reload docker` before
  bootstrap-servers activates live-restore.
- Interaction with `config_strategy: COPY_ALWAYS` (`all.yml:49`, passed as `KOLLA_CONFIG_STRATEGY` in
  `docker_common_options`, `all.yml:156-157`). FACT (kolla image): every Kolla service container except `bifrost_deploy`
  (which runs `/sbin/init`, kolla `docker/bifrost/bifrost-deploy/Dockerfile.j2:29-30`) runs `kolla_set_configs` when it
  starts, and under `COPY_ALWAYS` that re-copies the files listed in its `config.json` from `/etc/kolla/<svc>/` and
  rewrites `/run_command` (kolla `docker/base/start.sh:11`, `docker/base/set_configs.py:315-332,559-565`; both files are
  changed in 2025.1, see [Kolla images](../../concepts/kolla-images.md); [Kolla images §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image)). A
  container that starts again after a Docker restart therefore **activates any config that was rendered but not yet
  applied**, for example by `kolla-ansible genconfig` (`kolla_ansible/cli/commands.py:113-125`) or a failed reconfigure. Removals
  are not applied: destinations of entries dropped from `config.json`, or of optional sources that are gone, stay in
  the container ([Kolla images §3.5](../../concepts/kolla-images.md#35-what-a-restart-applies)).

### 2.5 With `kolla_container_engine: podman`

FACT:
- The `podman` role has no `handlers/` directory and none of its tasks has `notify` (`podman/tasks/install.yml:1-48`,
  `podman/tasks/config.yml:1-77`). So no bootstrap task restarts a Podman service for a config change; changes to the
  `/etc/containers/*.conf.d` drop-ins are written and nothing else is done. When Podman reads them is NOT AVAILABLE
  (Podman behaviour).
- There is no mask step and no Debian/Ubuntu mask window ([§2.3](#23-the-debianubuntu-mask-window) is Docker only).
- `podman.socket` is started and enabled on every run (`podman/tasks/install.yml:24-29`).
- Container units depend on `network-online.target`, not on an engine service
  (`ansible/module_utils/kolla_systemd_worker.py:51-55`).
- NOT AVAILABLE: what a `podman` package upgrade does to running containers; the role takes the same snapshot and runs
  `podman start` afterwards (`podman/tasks/install.yml:4-10,31-48`).

---

## 3. `/etc/hosts` generation

```jinja
# ansible-collection-kolla roles/etc_hosts/tasks/etc-hosts.yml:30-34
{% for host in groups['baremetal'] %}
{% set api_interface = hostvars[host]['api_interface'] | replace('-', '_') %}
{% if host not in groups['bifrost'] or api_interface in hostvars[host].ansible_facts %}
{% set hostnames = [hostvars[host].ansible_facts.nodename, hostvars[host].ansible_facts.hostname] %}
{{ 'api' | kolla_address(host) }} {{ hostnames | unique | join(' ') }}
```
Between 2024.1 and 2025.1 the `etc_hosts` role changed only in YAML spelling (`yes`/`True` written `true`) and in the
parentheses of the `api_interface` line, which renders the same value (a `diff -u` of the two collection trees).
- FACT: **it loops over all baremetal hosts**. Adding a host changes the managed block on **every** host
  bootstrap-servers runs
  against. No handler or restart is attached, so a change restarts nothing by itself.
- FACT: it needs facts for **all** baremetal hosts. `kolla_address` raises
  `FilterError("Interface ... not present on host ...")`
  when `hostvars[host]['ansible_facts']` lacks the interface (`kolla_ansible/kolla_address.py:107-114`). A host whose
  facts were never gathered (for example unreachable during fact gathering, with no fact cache) has an empty
  `ansible_facts` (ansible-core 2.18.20 `lib/ansible/vars/manager.py:311-312`, `lib/ansible/vars/clean.py:159-168`). So
  **one fact-less baremetal host outside `bifrost` fails this task on every host**: `FilterError` is an
  `AnsibleFilterError` (`kolla_ansible/exception.py:23`), and an `AnsibleError` fails the task (ansible-core 2.18.20
  `lib/ansible/executor/task_executor.py:209-210`). Those hosts then run no further task of the play
  (`lib/ansible/executor/play_iterator.py:504-515`), and since `etc_hosts` runs first (`baremetal/tasks/main.yml:2-3`),
  no bootstrap task runs at all. In practice every baremetal host must be reachable, or have cached facts, for
  bootstrap-servers.
- The template applies the same `-`→`_` replacement as the `when:` clause (`etc-hosts.yml:31,41`).
- With `--limit new-hosts`, only the limited hosts get the full list. **Existing hosts never learn the new names.** The
  docs
  require including all controllers in the limit for RabbitMQ (`doc/source/user/adding-and-removing-hosts.rst:22-29`).
  For
  computes, without `libvirt_tls` the libvirt connection and migration addresses are IPs
  (`nova.conf.d/libvirt.conf.j2:7-8`). **Exception:** with
  `libvirt_tls`, `live_migration_inbound_addr = migration_hostname = ansible_facts.nodename`
  (`roles/nova-cell/templates/nova.conf.d/libvirt.conf.j2:2-5`, `roles/nova-cell/defaults/main.yml:570`). NOT AVAILABLE:
  whether
  live migration from old computes to a new compute then fails without name resolution. To make the new name resolvable
  on the old computes, re-run bootstrap-servers on all computes (or use DNS).
- NOT AVAILABLE: whether running host-network containers see new `/etc/hosts` entries before they are recreated (the
  task edits the host's `/etc/hosts` only).
- Disable the whole mechanism with `customize_etc_hosts: false` (`etc_hosts/defaults/main.yml:3`,
  `etc_hosts/tasks/main.yml:2-4`)
  when DNS is authoritative. At large N, this also removes the O(N²) templating.

---

## 4. `ansible/gather-facts.yml` (confirmed) and its cost model

```yaml
# gather-facts.yml:5-26 (play 1, hosts: all, serial: kolla_serial)
- group_by: key: "all_using_limit_{{ (ansible_play_batch | length) != (groups['all'] | length) }}"
- setup: {filter: kolla_ansible_setup_filter, gather_subset: kolla_ansible_setup_gather_subset}
  when: not ansible_facts
# gather-facts.yml:34-62 (play 2, hosts: all_using_limit_True)
vars:
  batch_index: "{{ ansible_play_batch.index(inventory_hostname) }}"
  batch_size: "{{ ansible_play_batch | length }}"
  delegate_hosts: "{{ kolla_ansible_delegate_facts_hosts[batch_index | int::batch_size | int] }}"
setup: ... delegate_facts: True, delegate_to: "{{ item }}", with_items: "{{ delegate_hosts }}"
when: [item not in groups["all_using_limit_True"], not hostvars[item].ansible_facts]
```
Both plays carry `max_fail_percentage`, default 100 (`gather-facts.yml:7-10,36-39`). **Changed in 2025.1:** play 2 no
longer slices `groups['all']` but `kolla_ansible_delegate_facts_hosts` (`gather-facts.yml:47`), which defaults to
`groups['all']` (`group_vars/all.yml:43`); setting it to a shorter list shrinks the delegated work described below.
Cost model, with N = the length of `kolla_ansible_delegate_facts_hosts`, by default |groups['all']| (this **includes
`localhost`** from `[deployment]`), and L = hosts selected by
`--limit`:
- **No limit, serial 0:** play 1 runs N `setup` calls in parallel (forks). Play 2 is empty.
- **`--limit` with L hosts:** play 1 runs L parallel `setup` calls. Play 2 runs on the same L hosts. Limited host *i*
  loops
  **sequentially** over `kolla_ansible_delegate_facts_hosts[i::L]`, about N/L items, each a delegated `setup` (SSH from the deploy host to
  the
  *item* host, facts stored on the item); items that are themselves limited hosts are skipped (`gather-facts.yml:59`).
  The items of one host's loop run one after another (ansible-core 2.18.20
  `lib/ansible/executor/task_executor.py:299,347`). Total is N−L delegated setups, but only **L run at the same time**.
  The resulting wall time is NOT AVAILABLE. **L=1 means fully serial fact gathering of the whole inventory.**
- **With `kolla_serial` (no limit):** each batch is smaller than N, so every host joins `all_using_limit_True`, and
  every item of play 2 is then skipped by `item not in groups["all_using_limit_True"]` (loop evaluation only, no SSH).
- **With fact caching** (`gathering = smart` + `fact_caching`, `ansible-tuning.rst:36-66`): `when: not ansible_facts` is
  false
  for cached hosts, so both plays skip `setup`. The guide also documents populating the cache with
  `kolla-ansible gather-facts` without a limit before a limited command (`ansible-tuning.rst:68-85`;
  `kolla_ansible/cli/commands.py:80-88`). **New in 2025.1**, the guide documents the second way: set
  `kolla_ansible_delegate_facts_hosts` to the hosts whose facts are really needed, permanently or with `-e`
  (`ansible-tuning.rst:164-203`). Its rules of thumb: controllers are almost always needed, Prometheus needs every
  host unless `prometheus_target_address` is set per host, `/etc/hosts` during `bootstrap-servers` needs every host,
  and computes are fairly independent (`:189-203`). Which other templates read facts of hosts outside that list is
  NOT AVAILABLE beyond these rules. Stale-cache
  risk: IP or interface changes will not be seen until the cache expires (`fact_caching_timeout`).
- FACT: an unreachable *other* host without cached facts makes its delegated item in play 2 return `unreachable`
  (ansible-core 2.18.20 `lib/ansible/executor/task_executor.py:679-680`). One unreachable item makes the whole task
  result
  unreachable (`lib/ansible/executor/task_executor.py:141-146`, `lib/ansible/executor/task_result.py:71-72,95-105`), so
  the **limited** host is marked unreachable and removed from the play
  (`lib/ansible/plugins/strategy/__init__.py:624-628`)
  and from every later play (`lib/ansible/executor/playbook_executor.py:172,212`). So `--limit newnode` can fail
  because an unrelated node is down.
- FACT: `kolla_ansible_setup_filter` and `kolla_ansible_setup_gather_subset` apply **only** in `gather-facts.yml`.
  Playbooks that do
  not import it (`destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`,
  `octavia-certificates.yml`,
  and `certificates.yml` when none of `kolla_enable_tls_backend`, `rabbitmq_enable_tls`, `certificates_generate_libvirt`
  is true, `certificates.yml:2-6`) use implicit full play-level fact gathering.
- FACT: the documented filter `"ansible_[!qt]*"` (`ansible-tuning.rst:119`, aimed at "virtual interfaces beginning with
  q
  or t", :114-115) also hides real interfaces whose names start with `q` or `t` (for example `team0`, `trunk0`, `tun0`).
  `setup` keeps only the `ansible_`-prefixed fact names that match the filter, and each interface's facts sit under its
  name
  (ansible-core 2.18.20 `lib/ansible/modules/setup.py:195,209-215`,
  `lib/ansible/module_utils/facts/ansible_collector.py:57-75`,
  `lib/ansible/module_utils/facts/network/linux.py:55-56`). `kolla_address` then fails for `api_interface`,
  `tunnel_interface` and so on if they are named that way (`kolla_ansible/kolla_address.py:107-114`).

---
## 5. `ansible/roles/prechecks` (`kolla-ansible prechecks`)

- FACT: `prechecks` runs `site.yml` with `-e kolla_action=precheck` (`kolla_ansible/cli/commands.py:99-110`). The common
  `prechecks` role runs on `hosts: kolla_action_precheck`, which is **all** hosts (`site.yml:7-18,77-86`). Each service
  play then runs its own `<role>/tasks/precheck.yml` (54 files, about 2.9k lines in total).
- The common role (`roles/prechecks/tasks/main.yml:1-23`) checks:
  - inventory: the `loadbalancer` group exists and is non-empty when `enable_loadbalancer` (`inventory_checks.yml`).
  - host OS (`host_os_checks.yml`). **Changed in 2025.1:** CentOS Stream 9 and 10, Debian bookworm, Rocky 9 and 10, and
    Ubuntu noble (`vars/main.yml:11-21`); Debian bullseye, Ubuntu jammy and openEuler are no longer accepted. Can be
    skipped with `prechecks_enable_host_os_checks: false`.
  - **time sync** (skipped for `deployment` hosts): one of chrony, chronyd, ntp, ntpd or systemd-timesyncd must be
    active, and `timedatectl status` must say `synchronized: yes` (`timesync_checks.yml:2-47`). Can be skipped with
    `prechecks_enable_host_ntp_checks: false` (`defaults/main.yml:6`).
  - `/etc/localtime` exists, plus `/etc/timezone` on Debian (`datetime_checks.yml`).
  - `api_interface` present, active, with an address (`port_checks.yml`; skipped for `deployment` group hosts,
    `main.yml:13-15`).
  - systemd is the service manager (`service_checks.yml:2-7`); `docker --version` ≥ 18.09, only with Docker
    (`service_checks.yml:9-22`, `vars/main.yml:2`); Docker SDK ≥ 3.4.1, also only with Docker, `dbus` importable
    (baremetal only, both engines) and **Ansible 2.17–2.18, changed in 2025.1** (`package_checks.yml:2-32`,
    `vars/main.yml:3-5`).
  - empty values in passwords.yml (`grep`, `delegate_to: localhost`, `run_once`) (`service_checks.yml:24-32`; passes
    vacuously if the vault is encrypted, per the note above the task).
  - fails if `nscd` is running (`service_checks.yml:34-48`).
  - TLS VIP consistency and `enable_ceph` removed (`service_checks.yml:50-65`). **Changed in 2025.1:** the two RabbitMQ
    variable checks of 2024.1 are gone from this file ([F17](../findings.md#f17)); the RabbitMQ role's own precheck
    now fails when queues of the running broker are not of the type the configuration expects (quorum, transient
    quorum, stream), under the tag `rabbitmq-ha-precheck` (`roles/rabbitmq/tasks/precheck.yml:109-164`), which the CI
    upgrade job skips before migrating the queues (`tests/upgrade.sh:21-22`).
  - `config_owner_user` and group exist; passwordless sudo works (`user_checks.yml`).
  - external DB reachable when `enable_mariadb` is false (`database_checks.yml`).
- Service prechecks use `kolla_container_facts` (with `container_engine`), `wait_for ... state: stopped timeout: 1`
  port checks (skipped when the owning container already exists, for example
  `roles/nova-cell/tasks/precheck.yml:8-20,32-43`), `stat`, `getent`, `vgs`, `ping` of the VIP, `ip addr`, a read-only
  HAProxy `show stat` via `{{ kolla_container_engine }} exec` (`roles/loadbalancer/tasks/precheck.yml:230-236`), and
  read-only `rabbitmqctl list_queues` via `{{ kolla_container_engine }} exec` (`roles/rabbitmq/tasks/precheck.yml:109-164`).
- **Does it change anything?** FACT: no module that modifies state was found. Every `command`/`shell` read is
  `changed_when: false` or read-only, and there are no `template`/`copy`/`file`/`kolla_container`/`lineinfile`/`sysctl`/
  `service`/`systemd` tasks in the precheck files (grep; the one `service:` hit,
  `roles/letsencrypt/tasks/precheck.yml:13`, is a variable name). It is **safe on a running production cloud**.
- **Cost:** O(1) tasks per host per enabled service, plus full `gather-facts.yml`. Loops over other hosts exist only for
  `rabbitmq` hostname resolution (`roles/rabbitmq/tasks/precheck.yml:62-78`, for the rabbitmq hosts only) and the
  external-database check (`database_checks.yml:7`). There is no N² behaviour. The dominant cost at scale is Ansible's
  per-task overhead across 71 plays (51 in `site.yml` plus 20 imported from `gather-facts.yml`, `mariadb.yml`,
  `rabbitmq.yml`, `nova.yml`; the swift play is gone and the valkey play is new, `site.yml:399`;
  [Generated inventory](../generated-inventory.md)). Prechecks plays inherit `serial: kolla_serial` from site.yml where
  it is set.

---

## 6. `destroy` (`ansible/destroy.yml`, role `destroy`, `tools/cleanup-*`)

```yaml
# ansible/destroy.yml:1-9
- name: Apply role destroy
  hosts: all          # includes localhost/[deployment] in the sample multinode inventory
  max_fail_percentage: "{{ destroy_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}"
  roles: [destroy]    # no serial, implicit gather_facts, no gather-facts.yml import
```
- CLI: needs `--yes-i-really-really-mean-it` (`kolla_ansible/cli/commands.py:325-330`, `required=True`).
  `--include-images` sets `destroy_include_images=yes` and `--include-dev` sets `destroy_include_dev=yes`, both now
  plain flags (`:331-340, :350-355`). **Changed in 2025.1:** the 2024.1 `--include-dev` parsing bug is gone with the
  Bash wrapper, and the CLI no longer passes `inventories_comma_separated` ([§11](#11-kolla-ansible-cli)).
- Role flow (`roles/destroy/tasks/main.yml:1-8`): `validate_docker_execute.yml` (`sudo $CONTAINER_ENGINE ps`), then
  `cleanup-containers <engine>`, then `cleanup-images --all -e <engine>` (only if `destroy_include_images`, default
  `enable_destroy_images: "no"`, `all.yml:984`), then `cleanup-host` (`become: true`, environment variables passed in
  `cleanup_host.yml:5-16`) and, for Octavia health-manager hosts with auto-configured tenant networking, removal of
  the `octavia-interface` service and dhclient config (`cleanup_host.yml:18-41`). The engine is
  `kolla_container_engine` (`cleanup_containers.yml:3`, `cleanup_images.yml:3`). The role ignores `kolla_action` and
  has no tags.
- `tools/cleanup-containers` (unchanged from 2024.1):
  - Safety guard (16-22): **aborts if `nova_libvirt` is running and non-Xen-dom0 qemu processes exist**.
  - If `openvswitch_vswitchd` is among the containers and `neutron_openvswitch_agent` is running: `neutron-ovs-cleanup
    --ovs_all_ports`, then **delete every OVS bridge** (35-41). NOT AVAILABLE: whether the `exec -it` at line 40 fails
    without a TTY under Ansible's `script`, and so whether bridges survive.
  - For every **kolla-labelled container**: `systemctl disable` its unit, then `systemctl stop` it, then
    `reset-failed` if the unit is failed (43-49); then `rm -v -f`s them (52), disconnects them from the host network
    (54-57), then `volume rm` **every volume mounted by them** (29-32, 60). That includes `mariadb`, `rabbitmq`,
    `nova_compute` (instance disks when the default volume is used), `libvirtd`, `kolla_logs` and so on. It also
    removes the `/var/log/kolla` link (63) and every `/etc/systemd/system/kolla-*-container.service` unit file, then
    runs `systemctl daemon-reload` (66-67).
- `tools/cleanup-host`:
  - **Deletes ALL network namespaces** (`ip netns list`, 5-8). This is not limited to kolla's. NOT AVAILABLE: whether
    `ip netns list` prints lines of the form `name (id: N)`; the unquoted `$line` (line 7) would pass those extra
    words to `ip netns delete`.
  - Deletes every link whose `ip -o link` line matches `/tap/`, `/brq/` or `/vxlan/` (10-23).
  - Removes the VIPs from interfaces when `enable_haproxy == yes` (27-35).
  - Copies `/etc/fstab` to `/etc/fstab_backup` (37-38). **Changed in 2025.1:** the Swift block that fed whole fstab
    lines to `umount` and deleted them is gone with the Swift role; nothing else in the script reads the backup.
  - `rm -rfv` of custom datadirs when they differ from the default volume names (40-63): glance, nova_compute,
    gnocchi, influxdb, opensearch. For example `nova_instance_datadir_volume` set to a host path means **instance
    storage is wiped**.
  - Runs the OVS-DPDK uninstall script if present (67-70).
  - **`rm -rfv /etc/kolla/*` except `passwords.yml`, `globals.yml`, `globals.d`, `kolla-build.conf`, `config`,
    `certificates`** and any entry whose path is string-equal to one of the inventory sources (72-97). The comparison
    is `[ "$dir" == "$inventory" ]` (77) against `$dir` = `/etc/kolla/<name>`. **Changed in 2025.1:** the list now
    comes from Ansible's `ansible_inventory_sources` (`cleanup_host.yml:16`), not from the CLI. ansible-core turns each
    `-i` path into an absolute, normalised path relative to the current directory, without resolving symlinks
    (ansible-core 2.18.20 `lib/ansible/cli/__init__.py:430`, `lib/ansible/utils/path.py:30-62`), and exposes the list as
    `ansible_inventory_sources` (`lib/ansible/utils/vars.py:230-249`). So a relative `-i multinode` given from
    `/etc/kolla` now protects `/etc/kolla/multinode`; an inventory inside a subdirectory such as
    `/etc/kolla/inventory/hosts` still matches no entry, and that entry is removed. Without `-i` the CLI passes
    `<configdir>/ansible/inventory/all-in-one` (`kolla_ansible/ansible.py:144-152`), so with the default `/etc/kolla`
    the whole `/etc/kolla/ansible` entry is removed. The path is hard-coded (`FOLDER_PATH="/etc/kolla"`, 65) and ignores
    `node_config_directory`. Because `localhost` is in `hosts: all`, this also runs on the **deploy host** unless
    `--limit` excludes it, which deletes `admin-openrc.sh`, the other openrc files, `clouds.yaml` and anything else
    stored under `/etc/kolla`.
  - FACT: since `ansible_inventory_sources` is always set by ansible-core, running `destroy.yml` with
    `ansible-playbook` directly no longer leaves the template at `cleanup_host.yml:16` undefined, as it did in 2024.1.
- `tools/cleanup-images`: `--all` runs `rmi -f` on every kolla-labelled image (60-63, 94); the engine comes from `-e`.
- Scale and safety: per host, all hosts in parallel (forks), **no serial and no batch protection**. Never run it on
  production without `--limit`. For decommissioning, the docs use `stop` plus inventory removal, **not** `destroy`
  (`doc/source/user/adding-and-removing-hosts.rst:144-150,211-217`).
- CI: no 2025.1 CI job runs `destroy` (grep of `tests/` and `zuul.d/`).

### 6.1 `migrate-container-engine` (new in 2025.1)

A second command now removes containers and engine data on every host. FACT:
- The playbook imports `gather-facts.yml`, runs the `container-engine-migration` role on `hosts: baremetal` with no
  `serial`, then imports `site.yml` with `kolla_action: deploy` and `migration_flag`, then `post-deploy.yml`
  (`migrate-container-engine.yml:1-21`). The CLI asks for no confirmation (`kolla_ansible/cli/commands.py:509-519`).
- The target engine is `kolla_container_engine` and the current one is the other engine
  (`roles/container-engine-migration/defaults/main.yml:15-17`). The role fails when the target engine's package is
  already installed (`check-migration.yml:7-15`, `any_errors_fatal: true`), installs the target engine and SDK roles
  from the collection (`install-target-engine.yml:2-8`), cleans the OVS bridges when Open vSwitch runs
  (`migrate-volumes.yml:9-12`), **stops every container** of the current engine (`:14-20`), moves the volumes to the
  target engine's directory, removes the RabbitMQ Mnesia tables (`:63-69`), then removes all containers and images
  with `ce-cleanup.sh` and runs the collection's `uninstall.yml` for the old SDK and engine
  (`uninstall-current-engine.yml:6-20`).
- The Docker `uninstall.yml` stops and disables `docker`, removes its packages, the `docker` group and the CNI
  directory, and removes `/var/lib/docker`, `/var/lib/containerd`, `/usr/libexec/docker` and `/etc/docker` on a
  best-effort basis (ansible-collection-kolla `roles/docker/tasks/uninstall.yml`, `docker/defaults/main.yml:76-80`).
- Without `serial`, every baremetal host stops all its containers in the same play, so the whole cloud, control plane
  and guests' network agents included, is down until the `site.yml` redeploy finishes. What happens to running guests
  while `nova_libvirt` is stopped is NOT AVAILABLE; the MariaDB consequence is in
  [Database operations](../../operations/database-operations.md).

## 7. `prune-images` (`ansible/prune-images.yml`, role `prune-images`)

```yaml
# ansible/prune-images.yml:1-13
- import_playbook: gather-facts.yml
- name: Apply role prune-images
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  max_fail_percentage: "{{ prune_images_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}"
  roles: [prune-images]
# roles/prune-images/tasks/main.yml:2-4: validate_docker_execute.yml, then prune_images.yml
# roles/prune-images/tasks/prune_images.yml:2-9 (Docker)
docker_prune: {images: yes, images_filters: {label: kolla_version}, timeout: "{{ docker_image_prune_timeout }}"}  # default 300
# roles/prune-images/tasks/prune_images.yml:13-16 (Podman)
command: podman image prune --force --filter 'label=kolla_version'
```
- CLI needs `--yes-i-really-really-mean-it` (`kolla_ansible/cli/commands.py:362-381`); the docs call it pruning
  "orphaned Docker images" (`doc/source/user/operating-kolla.rst:235-236`). The playbook and role are unchanged from
  2024.1.
- FACT: `docker_prune` is not an ansible-core module; ansible-core redirects it to `community.docker.docker_prune`
  (ansible-core 2.18.20 `lib/ansible/config/ansible_builtin_runtime.yml:745-746`). That collection is not in the
  sources. **Changed in 2025.1:** `requirements-core.yml` pins `community.docker <5` (`requirements-core.yml:18-20`) and
  `install-deps` always installs it (`kolla_ansible/ansible.py:307-318`); ansible-collection-kolla still declares no
  dependency (`galaxy.yml:15`, `dependencies: {}`). NOT AVAILABLE: whether `images: yes` removes only dangling images,
  and so whether **old-release images (for example `2024.1` after an upgrade to `2025.1`) are kept**.
- FACT: with Podman the role runs `podman image prune --force --filter 'label=kolla_version'`
  (`prune_images.yml:13-16`), a `command` task without `changed_when`, so it reports changed on every run
  (ansible-core 2.18.20 `lib/ansible/modules/command.py:337`). NOT AVAILABLE: which images Podman removes with these
  flags (Podman behaviour).
- To remove images of an old release explicitly, `tools/cleanup-images --image-version <value> -e <engine>` removes
  images whose `kolla_version` label equals that value (`tools/cleanup-images:75-77,94`); what value the images carry is
  NOT AVAILABLE here. Manual `docker rmi` (or `podman rmi`) also works.
- NOT AVAILABLE: whether Docker would prune an image that a container uses (Docker behaviour). Cost is one engine call
  per host, plus the full `gather-facts.yml` (which is not needed by the role, but is imported and pays the --limit
  fact cost from [§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)).
- CI: not covered (grep of `tests/` and `zuul.d/`).

## 8. `post-deploy` (`ansible/post-deploy.yml`)

- **Changed in 2025.1:** three plays on `hosts: localhost` (`post-deploy.yml:1-71`). The first, without fact
  gathering, stats `node_config` and sets `needs_root` when the invoking user cannot write there (`:2-13`); the other
  two gather facts and use `become: "{{ needs_root }}"` instead of a fixed `become: true`, and pass the same value to
  the Octavia openrc as `octavia_openrc_become` (`:19,31,40,49,58,66-71`). The `/etc/openstack` directory that 2024.1
  created is no longer created.
  - templates `roles/common/templates/clouds.yaml.j2` to `{{ node_config }}/clouds.yaml`, mode `0600` (`:15-25`).
  - templates `admin-openrc.sh`, `admin-openrc-system.sh`, `public-openrc.sh` and `public-openrc-system.sh` to
    `{{ node_config }}/`, owned by the invoking user's uid/gid, mode `0600` (`:27-64`), and, with `enable_octavia`,
    the Octavia openrc (`:66-71`).
  `node_config` = `CONFIG_DIR`, default `/etc/kolla` (`all.yml:10`).
- Contents (templates unchanged from 2024.1): `OS_PASSWORD={{ keystone_admin_password }}` in plaintext in every file.
  `admin-openrc.sh` uses `OS_AUTH_URL={{ keystone_internal_url }}` (the **internal** endpoint), `OS_INTERFACE=internal`,
  and optional `OS_CACERT` from `kolla_admin_openrc_cacert` (`admin-openrc.sh.j2:1-25`). The `-system` files use
  `OS_SYSTEM_SCOPE=all` (`admin-openrc-system.sh.j2:6`); the `public-` files use `keystone_public_url`
  (`public-openrc.sh.j2:11`). `clouds.yaml` holds four clouds, `kolla-admin`, `kolla-admin-system` (public Keystone
  URL), `kolla-admin-internal` and `kolla-admin-system-internal`, all with the admin password in plaintext
  (`clouds.yaml.j2:1-49`).
- No `kolla_action` is passed (`kolla_ansible/cli/commands.py:259-267`). Cost is O(1) and it is safe to re-run.
  **`destroy` deletes these files on the deploy host** ([§6](#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)).

## 9. `mariadb_backup.yml` and `mariadb_recovery.yml` (playbook level only)

```yaml
# ansible/mariadb_backup.yml:1-11
- name: Backup MariaDB
  hosts: mariadb
  max_fail_percentage: ...   # default 100
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariabackup | bool }]
# ansible/mariadb_recovery.yml:1-13
- name: Recover mariadb
  hosts: mariadb
  max_fail_percentage: ...   # default 100
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariadb | bool }]
  vars: { mariadb_recover: true }
```
- CLI, **renamed in 2025.1:** `mariadb-backup` passes `-e kolla_action=backup -e mariadb_backup_type={full|incremental}`
  (`--full` is the default) and `mariadb-recovery` passes `-e kolla_action=deploy`
  (`kolla_ansible/cli/commands.py:437-481`; names at `setup.cfg:72-73`). `common` is its own play in `site.yml`
  (`site.yml:88-103`), and these two playbooks hold only the mariadb play, so `common` does not run. The playbooks
  themselves are unchanged from 2024.1.
- Neither playbook imports `gather-facts.yml`, and neither has `serial`. Implicit full fact gathering covers the
  **mariadb hosts only**.
- Backup runs only on `mariadb_backup_host` = `groups[mariadb_shard_group][0]` (`roles/mariadb/defaults/main.yml:123`,
  `group_vars/all.yml:553`), and only where `mariadb_backup_possible` (`roles/mariadb/defaults/main.yml:127`;
  `roles/mariadb/tasks/backup.yml:34-36`). It requires `enable_mariabackup: yes` (default `no`, `all.yml:922`).
  Otherwise every task is skipped silently.
- **Image-tag pitfall:** still does not apply in 2025.1. The backup container uses the image of the running `mariadb`
  container, or the configured mariadb image (`roles/mariadb/tasks/backup.yml:19-22`), and `openstack_tag` does not
  depend on facts registered only in `site.yml` (`group_vars/all.yml:795-798`). See
  [Database operations](../../operations/database-operations.md) for the backup and recovery tasks themselves,
  including the changed 2025.1 backup layout.
- CI: `mariadb-recovery` is tested with `--tags mariadb --skip-tags common` (`tests/test-mariadb.sh:21-25`).
  **New in 2025.1**, `mariadb-backup --full` and `--incremental` are tested too (`tests/test-mariadb.sh:35,45`).

## 10. `certificates.yml` (playbook level)

```yaml
# ansible/certificates.yml:1-11
- import_playbook: gather-facts.yml
  when: kolla_enable_tls_backend | default(false) | bool or rabbitmq_enable_tls | default(false) | bool
        or certificates_generate_libvirt | default(libvirt_tls) | default(false) | bool
- name: Apply role certificates
  hosts: localhost
  roles: [certificates]
```
- Unchanged from 2024.1. It runs on the deploy host only. Facts of all hosts are needed for the backend certificate's
  SAN list, which loops over `groups['tls-backend']` with `kolla_address`
  (`roles/certificates/templates/openssl-kolla-backend.cnf.j2:16-18`). The sample multinode inventory puts `network`
  as well as `control` in `tls-backend` (`ansible/inventory/multinode:42-44`).
- FACT: every openssl step is guarded with `creates:` (for example `generate-backend.yml:21,32,48`;
  `generate.yml:28,39,55,127,138,154`), so re-runs never regenerate. **FACT:** after adding a `tls-backend` host, the
  backend cert keeps its old SANs until `backend.csr`/`backend.crt` are deleted by hand. The SAN config is re-templated
  (`generate-backend.yml:8-14`), but the CSR and certificate steps are skipped while those files exist (`:23-32,34-48`;
  the `command` module exits without running when the `creates` path exists, ansible-core 2.18.20
  `lib/ansible/modules/command.py:319-325`). The external and internal certificate copies are skipped when
  `enable_letsencrypt` is on (`generate.yml:96-98,107-111,172-175`). The CLI still marks this command "For Development
  Only" (`kolla_ansible/cli/commands.py:187-195`).

---

## 11. `kolla-ansible` CLI

**Changed in 2025.1:** the Bash script `tools/kolla-ansible` is gone. `kolla-ansible` is a Python `cliff` application
(`kolla_ansible/cli/commands.py`, `kolla_ansible/ansible.py`); the sub-command comes first and its options follow it.
The full argument order, the command table and the option list are in
[Repository architecture §2](../../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook). What matters
for this sheet [CODE]:

- **Options.** `--tags`, `--skip-tags`, `--limit`, `-e`, the vault options, `--check`, `--diff` and the new `--become`
  pass straight through to `ansible-playbook` (`kolla_ansible/ansible.py:269-280`). `--forks` and the `EXTRA_OPTS`
  environment variable are gone. Every sub-command that runs a playbook accepts `--tags`; whether they mean anything
  depends on the playbook: `kolla-host.yml` only has the `baremetal` tag, and `destroy`/`prune-images`/`post-deploy`
  have no role tags.
- **Inventory.** `-i` may be given several times; without it the CLI passes `<configdir>/ansible/inventory/all-in-one`
  and exits if that path is not readable (`kolla_ansible/ansible.py:144-152, :167-180, :242-244`). In 2024.1 a command
  without `-i` passed no inventory at all.
- **`kolla_serial`.** `ANSIBLE_SERIAL` is now a module constant with the value 0, not an environment variable
  (`kolla_ansible/cli/commands.py:20-22`). Only `upgrade` (`:278`) and `reconfigure` (`:136`) pass it, as
  `kolla_serial=0`, after the user's `-e` options (`kolla_ansible/ansible.py:261-266`), and Ansible's last-wins rule
  for extra-vars (ansible-core 2.18.20 `lib/ansible/utils/vars.py:198-221`) means **`kolla-ansible reconfigure -e
  kolla_serial=1` and `kolla-ansible upgrade -e kolla_serial=1` run with `0`, and there is no longer any way to batch
  them** ([F19](../findings.md#f19)). For every other command, `-e kolla_serial=...` works, `bootstrap-servers`
  included (`bootstrap-servers.rst:83`). Plays that **ignore** `kolla_serial` are listed below.
  - `site.yml`: "Group hosts based on configuration" (`:7`), prechecks (`:77`), etcd (`:485`, no `serial`), and
    cyborg, whose play reads `serial: '{{ serial|default("0") }}'` (`site.yml:874`). In the imported `mariadb.yml` and
    `rabbitmq.yml`, the restart plays use a fixed `serial: "33%"` (`mariadb.yml:24,42`, `rabbitmq.yml:36`) and the
    other plays have no `serial`. The two imported gather-facts plays do use `kolla_serial` (`gather-facts.yml:11,40`),
    as do all `nova.yml` plays and `nova-libvirt-cleanup.yml:8`.
  - `destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, `certificates.yml`,
    `octavia-certificates.yml`, `bifrost.yml`, `rabbitmq-reset-state.yml`, `rabbitmq-upgrade.yml` and the new
    `migrate-container-engine.yml` and `migrate-valkey.yml` (grep `serial:` count 0).
- **The three 2024.1 CLI bugs are gone with the Bash wrapper** [CODE]: `--ask-vault-pass` no longer overwrites the
  verbosity (the vault options are `--vault-id`, `--vault-password-file` and `-J`/`--ask-vault-password`,
  `kolla_ansible/ansible.py:102-124`); `--include-dev` is a plain flag (`kolla_ansible/cli/commands.py:331-335`); and the
  command is run as an argument list, not as an unquoted string (`kolla_ansible/utils.py:174-191`).
- **Environment check.** The CLI no longer checks the Ansible version itself; the supported range is the
  `ansible-core>=2.17,<2.19` requirement (`requirements.txt:13`) and the prechecks' 2.17–2.18 test
  (`roles/prechecks/vars/main.yml:4-5`).
- **Confirmation guard.** `stop`, `destroy` and `prune-images` require `--yes-i-really-really-mean-it`
  (`kolla_ansible/cli/commands.py:292, :325, :369`). `bootstrap-servers` (which can restart Docker everywhere),
  `nova-libvirt-cleanup` and the new `migrate-container-engine` (which stops every container,
  [§6.1](#61-migrate-container-engine-new-in-20251)) have **no** confirmation.
- **Commands, 2025.1 versus 2024.1:** `mariadb_backup` and `mariadb_recovery` are renamed `mariadb-backup` and
  `mariadb-recovery`; `check`, `migrate-container-engine` and `migrate-valkey` are new; `rabbitmq-upgrade` and
  `bash-completion` are no longer commands (`setup.cfg:50-77`). `octavia-certificates --check-expiry <days>` passes
  `-e octavia_certs_check_expiry=yes -e octavia_certs_expiry_limit=<days>` (`kolla_ansible/cli/commands.py:198-228`);
  the role then only reads the three certificates under `{{ node_custom_config }}/octavia/` on the deploy host and
  fails if one expires within that many days (`roles/octavia-certificates/tasks/check_expiry.yml:1-24`).
  `nova-libvirt-cleanup` runs `nova-libvirt-cleanup.yml` on `hosts: compute` with `kolla_serial`
  (`nova-libvirt-cleanup.yml:4-18`).

---

## 12. Ansible configuration and documented tuning

- FACT: **no `ansible.cfg` ships for users.** Repo-wide search found only:
  - `tests/templates/ansible.cfg.j2:1-13` (CI, unchanged from 2024.1): `callback_plugins` only when the change message
    contains `#ara` (2-4), `callbacks_enabled = default,profile_tasks,timer` (5), `host_key_checking = False`,
    `inject_facts_as_vars = False`; `[ssh_connection] pipelining = True`, `retries = 3`,
    `ssh_args = -C -o ControlMaster=auto -o ControlPersist=300` (10-13).
  - `contrib/dev/vagrant/bootstrap.sh:250-257` (dev): `forks=100`, `remote_user = root`, `scp_if_ssh=True`.
- Documentation recommendations:
  - `doc/source/user/quickstart.rst` contains no `ansible.cfg` (grep for `ansible.cfg`, `pipelining`, `forks` is
    empty); it points to `kolla-ansible install-deps` for the collections (`quickstart.rst:128`).
  - `doc/source/user/ansible-tuning.rst`:
    - SSH pipelining `[ssh_connection] pipelining = True` (8-18).
    - `forks = 20` as an example; "experiment to find out the CPU, memory and IO limits" (20-34).
    - Fact caching: `gathering = smart`, `fact_caching = jsonfile`, `fact_caching_connection = /tmp/ansible-facts`, and
      an optional `fact_caching_timeout` (36-66); populating the cache with `kolla-ansible gather-facts` before a
      `--limit` run (68-85).
    - `inject_facts_as_vars = False` (87-104). A grep of 2025.1 `ansible/` for common injected fact names
      (`ansible_hostname`, `ansible_nodename`, `ansible_distribution`, `ansible_os_family`, `ansible_default_ipv4`,
      `ansible_interfaces` and others) outside `ansible_facts` finds none.
    - Fact filtering `kolla_ansible_setup_filter: "ansible_[!qt]*"`, "reported to be as large as 18x" (106-129).
    - `kolla_ansible_setup_gather_subset: "all,!facter"` (131-141).
    - "Max failure percentage", `kolla_max_fail_percentage` and `<service>_max_fail_percentage`, undefined by default,
      "equivalent to a value of 100" (143-162).
    - **New in 2025.1:** "Delegated fact gathering", `kolla_ansible_delegate_facts_hosts` (164-203;
      [§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)).
  - **Not documented anywhere in `doc/source`:** ControlPersist/`ssh_args`, mitogen, `strategy` (free/linear), or
    `serial` for scale. The only `kolla_serial` mention is `bootstrap-servers.rst:83`. Large-scale guidance amounts
    to `--limit` per cell (`doc/source/reference/compute/nova-cells-guide.rst:376-394,426-449`) and the tuning page
    above.

---

## 13. Day-2 and scale knobs: `etc/kolla/globals.yml` and `ansible/group_vars/all.yml`

Defaults live in `all.yml` and, for bootstrap knobs, in the ansible-collection-kolla role defaults. `globals.yml` shows
commented examples. **Several Docker knobs are not listed in globals.yml at all** (`docker_log_max_*`,
`docker_disable_*`, `docker_custom_config`, `docker_graceful_timeout`, `docker_restart_policy`, `docker_*_proxy`,
`docker_registry_ca`, `docker_registry_mirrors`, `docker_debug`, `docker_apt_key_env`,
`kolla_ansible_delegate_facts_hosts`, and every `podman_*` variable; grep), but they can still be overridden there.

| Knob | Default (file:line) | Day-2 / scale relevance |
|---|---|---|
| `kolla_container_engine` | `docker` (`all.yml:100`; `globals.yml:91-92`) | `podman` switches bootstrap to the `podman`/`podman_sdk` roles ([§1](#1-ansiblekolla-hostyml-the-bootstrap-servers-command)) and every container to the Podman worker. **New in 2025.1:** an existing deployment is switched with `kolla-ansible migrate-container-engine` ([§6.1](#61-migrate-container-engine-new-in-20251)). |
| `kolla_max_fail_percentage` / `<service>_max_fail_percentage` | undefined, read as 100 (`globals.yml:31`; e.g. `kolla-host.yml:8-11`) | Below 100, a play stops when more than that share of the current batch fails ([Controlled batches](../../operations/controlled-batches.md)) |
| `kolla_ansible_setup_filter` / `kolla_ansible_setup_gather_subset` | `omit` (`all.yml:31,37`; `globals.yml:19,25`) | Fact size and time per host. Biggest win on computes with many tap/qvo interfaces. |
| `kolla_ansible_delegate_facts_hosts` | `groups['all']` (`all.yml:43`) | **New in 2025.1.** The hosts whose facts a `--limit` run gathers by delegation ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| `config_strategy` | `COPY_ALWAYS` (`all.yml:49`; `globals.yml:43`) | Containers re-copy config at every start, so a container that starts again after a Docker restart or reboot applies pending rendered config ([§2.4](#24-blast-radius-of-a-restart)) |
| `openstack_release` / `openstack_tag` / `openstack_tag_suffix` | `2025.1` / `<release>-<distro>-<distro version><suffix>` / `""` (`all.yml:795-798`; `globals.yml:49-55`, whose commented `openstack_release` and `openstack_tag` examples differ from the `all.yml` defaults) | Image tag. Does not depend on `site.yml`-only facts ([§9](#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)). |
| `docker_registry`, `docker_registry_insecure`, `docker_namespace` | `quay.io` / `no` / `openstack.kolla` (`all.yml:106-111`; `globals.yml:100-107`, whose commented `docker_namespace` example is `kolla`) | `insecure-registries` does not follow the registry: changing `docker_registry` rewrites daemon.json (and restarts Docker on every host at the next bootstrap-servers) only when `docker_registry_insecure` is true or a `docker_registry_ca` is set. Not used by the `podman` role ([§1.2](#12-task-by-task-installyml)). |
| `docker_registry_mirrors` / `docker_debug` | `[]` / `false` (`docker/defaults/main.yml:64,74`) | In daemon.json, so setting either means a restart |
| `docker_log_max_file` / `docker_log_max_size` | `"5"` / `"50m"` (`all.yml:122-123`) | daemon.json, so a change means a restart |
| `docker_disable_default_iptables_rules` / `_network` / `ip_forward` | **`"yes"`** x3 (the last two follow the first, `all.yml:117-119`) | daemon.json, so a change means a restart. The first also drops `iptables` from the Docker package list (`docker/defaults/main.yml:32`). |
| `docker_storage_driver` / `docker_runtime_directory` / `docker_custom_config` | `""` / `""` / `{}` (`docker/defaults/main.yml:34-35`, `all.yml:112`) | In daemon.json (restart). `docker_runtime_directory` also sets both volume paths, `podman_volumes_path` included (`all.yml:165-167`) |
| `docker_http_proxy` / `docker_https_proxy` / `docker_no_proxy` | `""` (`docker/defaults/main.yml:37-39`) | systemd drop-in, **never applied by Kolla** ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |
| `docker_systemd_reload` | `false` (`docker/defaults/main.yml:71`) | `true` makes the handler reload instead of restart Docker |
| `docker_apt_package_pin` / `docker_yum_package_pin` | `""` (`docker/defaults/main.yml:15,26`) | Pins the Docker engine version; the package task stays `state: present` |
| `docker_restart_policy` / `docker_restart_policy_retry` | `unless-stopped` / `10` (`all.yml:126,129`) | Written into each container's systemd unit (`Restart=always` for `unless-stopped`); whether containers return after a daemon restart or reboot is NOT AVAILABLE ([§2.4](#24-blast-radius-of-a-restart)) |
| `docker_graceful_timeout` | `60` (`all.yml:148`) | Applied: the unit's `ExecStop` and the Docker worker's stops use it ([Repository architecture §6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). The stop timeout of a daemon restart is NOT AVAILABLE ([§2.4](#24-blast-radius-of-a-restart)). |
| `docker_client_timeout` | `120` (`all.yml:114`; `globals.yml:110`) | Applied: passed in `docker_common_options` (`all.yml:161`) and used for the unit's `StartLimitInterval` and the wait for a unit to reach its state (`module_utils/kolla_systemd_worker.py:28,65`) |
| `docker_configure_for_zun` / `containerd_configure_for_zun` | `no` (`all.yml:132,137`) | Zun hosts: no `cluster-store` in daemon.json (`all.yml:134`); the containerd config is overwritten and restarted |
| `docker_apt_key_env` | `{}` (`docker/defaults/main.yml:18`) | **New in 2025.1.** Environment of the Docker apt key download, for example a proxy |
| `customize_etc_hosts`, `create_kolla_user`, `disable_firewall`, `change_selinux`/`selinux_state`, `enable_docker_repo`, `virtualenv` | true, **false**, true, true/permissive, true, none (`etc_hosts/defaults/main.yml:3`, `baremetal/defaults/main.yml:20,25-30`, `docker/defaults/main.yml:6`, `docker_sdk/defaults/main.yml:47`) | Host mutations made by bootstrap-servers ([§1](#1-ansiblekolla-hostyml-the-bootstrap-servers-command)) |
| `enable_nova_libvirt_container` | `true` for kvm/qemu (`all.yml:945`) | Removes host libvirt packages (and `iscsi-initiator-utils` on RedHat) and disables the libvirtd AppArmor profile during bootstrap. `enable_chrony` does not exist (grep). |
| `neutron_plugin_agent` | `openvswitch` (`all.yml:332`; `globals.yml:165`) | Drives OVS and agent containers on every compute |
| `enable_neutron_dvr` / `neutron_compute_dvr_mode` / `computes_need_external_bridge` | `no` / `dvr` / derived (`all.yml:931,1223-1224`; `globals.yml:403`) | DVR puts L3 and metadata agents on **every compute**, and an external bridge per compute |
| `enable_neutron_agent_ha` | `no` (`all.yml:934`; `globals.yml:406`) | L3/DHCP agent HA on network nodes |
| `enable_neutron_provider_networks` | `no` (`all.yml:936`; `globals.yml:408`) | External bridge on computes |
| `nova_compute_virt_type` | `kvm` (`all.yml:1253`; `globals.yml:613`) | `nova_libvirt` is enabled for kvm and qemu |
| `enable_nova_ssh` | `yes` (`all.yml:947`) | nova_ssh container per compute (cold migration and resize) |
| `enable_cells` | `no` (`all.yml:859`; `globals.yml:337`) | Cell sharding for scale, together with `--limit cellNN` (nova-cells guide) |
| `openstack_service_workers` / `openstack_service_rpc_workers` | `min(vcpus,5)` / `min(vcpus,3)` (`all.yml:812-813`) | Caps API and RPC workers on large controllers (46 references in 29 roles under `ansible/roles/`, grep; 49 in 2024.1) |
| `database_max_pool_size` / `database_connection_recycle_time` | `1` / `10` (`all.yml:92-93`) | oslo.db pool per worker (used in the templates of 24 roles, grep, as in 2024.1) |
| `openstack_logging_debug` | `False` (`all.yml:799`; `globals.yml:312`) | Log volume. Combine with docker log rotation. |
| `enable_fluentd` / `enable_central_logging` | `yes` / `no` (`all.yml:879,860`) | Per-host fluentd container |
| `set_sysctl` / `kolla_sysctl_conf_path` | `yes` / `/etc/sysctl.conf` (`all.yml:816,819`) | Host sysctl writes from service `config-host.yml` (and the one bootstrap sysctl on RedHat) |
| `skip_stop_containers` | `[]` (`all.yml:993`) | Protects containers from `kolla-ansible stop` |
| `enable_destroy_images` | `no` (`all.yml:984`; `globals.yml:356`) | Whether destroy also removes images |
| `enable_mariabackup` | `no` (`all.yml:922`; `globals.yml:397`) | Must be `yes` or `mariadb_backup` silently does nothing |
| `kolla_enable_tls_backend` | `no` (`all.yml:1079`) | Pulls `gather-facts.yml` into `certificates` |
| `keepalived_virtual_router_id` | `51` (`all.yml:247`; `globals.yml:188`) | Must be unique per L2 segment in multi-region setups |
| `<container>_dimensions` | `default_container_dimensions` (`all.yml:201-223`; **changed in 2025.1:** nofile 1048576 for Docker on every distribution, `RLIMIT_NOFILE`/`RLIMIT_NPROC` 1048576 under Podman), combined per role (e.g. `roles/nova-cell/defaults/main.yml:280`); `globals.yml:194-200` | CPU, memory and ulimit limits per container |


---

## 14. Register of open questions (NOT AVAILABLE, or answered from code)

| # | Question | Status | What the code shows |
|---|---|---|---|
| H1 | Does daemon-reload report changed? | **Answered from code** (FACT) for ansible-core 2.18.20: no | ansible-core 2.18.20 `lib/ansible/modules/systemd.py:390-403` runs `daemon-reload` with `changed=False`; `changed` is set only at `:487,539,571`, so the reload handler never notifies the restart ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)). ansible-core 2.17 is NOT AVAILABLE. |
| H2 | Does an interrupted bootstrap leave docker masked on Debian/Ubuntu, so that docker does not start after reboot? | Symlink left in place unless the recovery block `docker/tasks/install.yml:47-75` or the "Restart docker" handler (both `masked: false`) already ran: FACT. Effect at reboot: NOT AVAILABLE. Docker only. | No `rescue`/`always` in the install path; a failed host runs no further task (ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:504-515`); systemd boot behaviour is not in the sources ([§2.3](#23-the-debianubuntu-mask-window)) |
| H3 | Does one fact-less baremetal host abort bootstrap-servers on all hosts (`/etc/hosts` task)? | **Answered from code** (FACT): yes, for a host outside `bifrost` with no gathered or cached facts | Empty `ansible_facts`, `kolla_address` raises on that host's line, and every host renders every line ([§3](#3-etchosts-generation)) |
| H4 | Does an unreachable non-limited host break `--limit` runs through delegated facts? | **Answered from code** (FACT): yes, unless its facts are cached or it is left out of `kolla_ansible_delegate_facts_hosts` (new in 2025.1) | Its delegated item returns `unreachable`, which removes the limited host from the run ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| H5 | What is the wall time of `--limit` fact gathering? | NOT AVAILABLE | Each limited host runs about N/L delegated `setup` calls one after another, L hosts in parallel ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| H6 | What stop timeout does a Docker daemon restart apply to Kolla containers? | NOT AVAILABLE | The Docker path sets no `StopTimeout`; `docker_graceful_timeout` reaches the systemd units and the Docker worker's stops only ([§2.4](#24-blast-radius-of-a-restart)) |
| H7 | Does a simultaneous Docker restart on all controllers need `mariadb-recovery`? | NOT AVAILABLE | All notified hosts restart Docker in the same handler flush; the image has no Galera recovery logic ([§2.4](#24-blast-radius-of-a-restart)) |
| H8 | Do QEMU guests survive a nova_libvirt container restart? | NOT AVAILABLE | `pid_mode: host`, `cgroupns_mode: host` and a `/sys/fs/cgroup` bind mount ([§2.4](#24-blast-radius-of-a-restart)) |
| H9 | Does `kolla-libvirt-guests.service` (optional) shut guests down on a Docker restart? | NOT AVAILABLE | `kolla-libvirt-guests-docker.service` has `Requires=docker.service`; `ExecStop` runs `libvirt-guests.sh shutdown` ([§2.4](#24-blast-radius-of-a-restart)) |
| H10 | Does an option set both in the drop-in and in daemon.json make dockerd fail at the next restart? | NOT AVAILABLE | The role writes both files and restarts Docker only for daemon.json (or CA) changes ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |
| H11 | Does `apparmor_parser -R` fail on an already-unloaded profile (second run)? | **Does not arise** (FACT): the task links the profile into `/etc/apparmor.d/disable/` and is skipped once that link exists | `apparmor_libvirt/tasks/remove-profile.yml:7-22`. Whether `apparmor_parser -R` fails on an unloaded profile remains NOT AVAILABLE, but the role does not run it twice ([§1.3](#13-task-by-task-post-installyml)) |
| H12 | Do mariadb-backup and mariadb-recovery use a mismatched image tag? | **Does not apply** (FACT) | The backup uses the running mariadb container's image (`roles/mariadb/tasks/backup.yml:19-22`, `group_vars/all.yml:795-798`) ([§9](#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)) |
| H13 | Is the backend TLS cert regenerated for new hosts? | **Answered from code** (FACT): no | `creates:` guards on the CSR and certificate steps ([§10](#10-certificatesyml-playbook-level)) |
| H14 | Does `kolla-ansible bootstrap-servers --check --diff --limit X` preview daemon.json changes safely? | NOT AVAILABLE | The CLI passes `--check`/`--diff` through (`kolla_ansible/ansible.py:269-280`). In check mode `copy` reports changed (with a diff) without writing (ansible-core 2.18.20 `lib/ansible/plugins/action/copy.py:283,344-383`), the systemd module runs no action (`lib/ansible/modules/systemd.py:397,494`), and `command` tasks without `creates`/`removes` are skipped (`lib/ansible/modules/command.py:346-353`), except those marked `check_mode: false` such as the new `docker system info` (`docker/tasks/config.yml:62`); the collection modules used by the role (`ufw`, `selinux`, `sysctl`, `authorized_key`, `git_config`) are outside the sources |
| H15 | Do running containers see `/etc/hosts` updates? | NOT AVAILABLE | The task edits the host's `/etc/hosts` only ([§3](#3-etchosts-generation)) |
| H16 | Does the `ansible_[!qt]*` filter break hosts whose api/tunnel interface starts with q or t? | **Answered from code** (FACT): yes | The filter is matched against fact names, and `kolla_address` raises for a missing interface ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| H17 | With Podman, does a change to the `/etc/containers/*.conf.d` drop-ins take effect, and when? | NOT AVAILABLE | The `podman` role writes them and notifies nothing (`podman/tasks/config.yml:13-53`) ([§2.5](#25-with-kolla_container_engine-podman)) |
| H18 | Does `destroy` keep an inventory stored under `/etc/kolla`? | **Answered from code** (FACT): only an inventory whose absolute path is exactly an entry of `/etc/kolla`; **changed in 2025.1**, a relative `-i` now counts after ansible-core makes it absolute | `tools/cleanup-host:72-97`, `cleanup_host.yml:16` ([§6](#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)) |
| H19 | Does `docker system info` fail the bootstrap on a host where the Docker daemon is not running? | NOT AVAILABLE. **New in 2025.1** | The task has no `failed_when` and runs before the unmask and the "Start and enable docker" task (`docker/tasks/config.yml:57-63,153-159`) ([§2.3](#23-the-debianubuntu-mask-window)) |
| H20 | What does the new containerd restart do to running containers on hosts that use Docker's containerd image store? | NOT AVAILABLE. **New in 2025.1** | `config.yml:69-87` renders `/etc/containerd/config.toml` and notifies "Restart containerd" ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |

## 15. Operational recommendations from this code

1. Before any `bootstrap-servers` re-run on production, render the target daemon.json and compare it with the hosts
   (`kolla-ansible bootstrap-servers --check --diff --limit <one host>`; whether check mode makes this safe is NOT
   AVAILABLE, H14). Expect a difference on EL10 hosts that carried `default-ulimits` and on any host whose
   `docker_custom_config` relied on the openEuler default. If it differs, run with `-e kolla_serial=1`, or with
   `--limit` per controller and in compute batches, keeping Galera and RabbitMQ quorum.
2. Do not rely on the systemd drop-in (`docker_*_proxy`, Zun options) being applied by Kolla. Put options in
   `docker_custom_config` (daemon.json) so changes are applied, and are applied visibly; schedule a controlled Docker
   restart after changing proxy settings.
3. After any failed or interrupted run on Debian/Ubuntu with Docker, check for a masked `docker.service`. Make sure
   Docker is running before a re-run: the new `docker system info` step needs it (H19).
4. Set `disable_firewall: false`, `change_selinux: false` and the package-removal lists (`ubuntu_pkg_removals`,
   `redhat_pkg_removals`) explicitly if the hosts are managed by other tooling. Check `open-iscsi` and
   `iscsi-initiator-utils` before the first run on hosts that use host iSCSI. Set `create_kolla_user: true` explicitly
   if you rely on the `kolla` user. On Debian/Ubuntu with Docker, expect an apt cache refresh on every run.
5. At scale, enable jsonfile fact caching with `gathering = smart`, `inject_facts_as_vars = False` and a setup filter,
   fill the cache with `kolla-ansible gather-facts` before `--limit` runs, and, new in 2025.1, narrow
   `kolla_ansible_delegate_facts_hosts` for compute-only limits. Without them, `--limit` runs gather facts for the
   whole inventory, one host at a time per limited host.
6. Do not count on batching `reconfigure` or `upgrade`: both always run with `kolla_serial=0` in 2025.1. Use
   `deploy -e kolla_serial=N` where batching matters ([F19](../findings.md#f19)). Pass `-i` explicitly so the
   inventory is the one you mean.
7. Never run `destroy` without `--limit`. Exclude the deploy host (`--limit '!localhost'`) unless you want its
   `/etc/kolla` wiped; an inventory under `/etc/kolla` survives only when it is passed with `-i` and sits directly in
   `/etc/kolla`.
8. Treat `migrate-container-engine` as a full outage of the cloud: it stops every container on every baremetal host in
   one play and asks for no confirmation ([§6.1](#61-migrate-container-engine-new-in-20251)).
9. With `kolla_container_engine: podman`, set `podman_registry` (and friends) yourself if you need a private registry
   configured on the hosts: kolla-ansible does not map `docker_registry` to them.

## Lab tests

These points are read from the code; a run on a lab installed in 2024.1 and upgraded to 2025.1 would confirm them.
They stay [NOT AVAILABLE] until such a run is recorded.

| Test | What the code does not settle |
|---|---|
| `bootstrap-servers` on a deployed 2024.1 cloud before the upgrade | which hosts restart Docker, and whether containers come back |
| `bootstrap-servers` with Docker stopped on one host | whether `docker system info` fails the host (H19) |
| A host with Docker's containerd image store | whether the containerd restart affects running containers (H20) |
| `destroy -i multinode` run from `/etc/kolla` | that the inventory file is kept and the other entries are removed |
| `migrate-container-engine` on a small lab | downtime, and what happens to running guests |

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
- [Database operations](../../operations/database-operations.md)
- [Repository architecture §2](../../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook), the 2025.1 CLI
- [Findings F16, F17 and F19](../findings.md#f16)
- [2024.1 fact sheet E](../../../2024.1/reference/factsheets/e-host-bootstrap-ops-playbooks/)

---
title: Fact sheet E
description: "Fact sheet for host bootstrap and operational playbooks: bootstrap-servers, prechecks, destroy, prune-images, fact gathering, CLI, tuning docs."
tags: [bootstrap-servers, prechecks, destroy, mariadb-backup, mariadb-recovery, facts, docker, serial, limit]
---

# Fact sheet E

Source: `kolla-ansible` at tag `2023.1-eol` (commit `4891a21`) and `ansible-collection-kolla` at tag `2023.1-eol`,
which provides the roles that `bootstrap-servers` runs (`ansible/kolla-host.yml:9-10`; `requirements.yml:2-5` pins
the collection to the git branch `unmaintained/2023.1`). Kolla-Ansible paths starting with `tools/`, `doc/`, `tests/`,
`etc/`, `kolla_ansible/` or `ansible/` are relative to the repo root; `roles/...`, `group_vars/...` and `*.yml`
playbooks are relative to `ansible/`. In §1–§3, `etc_hosts/…`, `baremetal/…`, `packages/…`, `docker/…`,
`kolla_user/…`, `docker_sdk/…` and `apparmor_libvirt/…` are ansible-collection-kolla `roles/<role>/…`.
Ansible behaviour claims cite **ansible-core 2.14.18** (as ansible-core 2.14.18 `lib/ansible/...`). 2023.1 accepts
ansible-core 2.13 to 2.14 (`tools/kolla-ansible:10-11,78-82`, `roles/prechecks/vars/main.yml:4-5`).

Labels: **FACT** = [CODE], read directly from the sources (cited): kolla-ansible, ansible-collection-kolla, the kolla
image repository (cited as kolla `docker/...`) or ansible-core. **NOT AVAILABLE** = [NOT AVAILABLE], these sources do
not establish it, often because it depends on Docker, systemd, Galera or libvirt behaviour, or on a module that lives in
an Ansible collection outside the sources (`ufw`, `selinux`, `sysctl`, `authorized_key`, `git_config`, `docker_prune`
are redirected out of ansible-core: ansible-core 2.14.18 `lib/ansible/config/ansible_builtin_runtime.yml`, e.g.
`:745-746` for `docker_prune`).

---

## 0. Most important findings

1. **When Docker restarts.** In 2023.1 the restart is a **handler**, "Restart docker" (`docker/handlers/main.yml:10-15`:
   `state: restarted`, or `reloaded` when `docker_systemd_reload` is true, default `false`,
   `docker/defaults/main.yml:63`;
   plus `masked: no`). Only two tasks notify it: the `/etc/docker/daemon.json` write (`docker/tasks/config.yml:9-47`)
   and the private-registry CA copy (`:98-108`, only when `docker_registry_ca` is set). The systemd drop-in tasks notify
   "Reload docker service file" (`docker/handlers/main.yml:2-8`), a `daemon_reload`-only systemd call that **never
   reports changed** (ansible-core 2.14.18 `lib/ansible/modules/systemd.py:384-395`; `changed` is set only at
   `:475,521,553`), and a handler notifies further handlers only when it reports changed
   (`lib/ansible/plugins/strategy/__init__.py:615-616`). **So Docker restarts if and only if the daemon.json write (or
   the CA copy) reports changed: the rendered content differs, or the file mode is not `0644`** (ansible-core 2.14.18
   `lib/ansible/plugins/action/copy.py:285,342-380`, `lib/ansible/module_utils/basic.py:912,963`). The handlers are
   flushed at `docker/tasks/config.yml:110-111`, on every notified host of the batch at once, and the batch is all
   hosts by default: `kolla_serial` defaults to `0` (`kolla-host.yml:6`) and the CLI never passes it for
   `bootstrap-servers` (`tools/kolla-ansible:471-475`). New default content: `iptables: false`, `bridge: none`,
   `ip-forward: false` (`docker_disable_default_iptables_rules: "yes"`, `group_vars/all.yml:108-110`) and, on EL9
   hosts, `default-ulimits` nofile (`docker/defaults/main.yml:47-49`). A host whose daemon.json differs from that (for
   example one bootstrapped by an older release) restarts Docker on its next `bootstrap-servers`.
   A host that fails after the daemon.json write and before the flush (drop-in or CA tasks, `config.yml:49-108`) never
   runs the notified handler: the role has no `force_handlers` (grep of ansible-collection-kolla `roles/` is empty),
   the default is `False` (ansible-core 2.14.18 `lib/ansible/config/base.yml:634-636`), and a failed host leaves the
   play (`lib/ansible/executor/play_iterator.py:468-478`, `lib/ansible/playbook/play.py:303-335`). The next run finds
   daemon.json unchanged, so **no Kolla task restarts Docker for that change**
   ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)).
2. **The systemd drop-in is never applied.** `docker_custom_option` no longer exists (grep of kolla-ansible and
   ansible-collection-kolla is empty). The drop-in `/etc/systemd/system/docker.service.d/kolla.conf` now carries
   `docker_http_proxy`/`docker_https_proxy`/`docker_no_proxy` and, on Zun compute hosts, `docker_zun_options`
   (`docker/templates/docker_systemd_service.j2:1-13`). Adding, changing or removing it does **not** restart Docker: it
   notifies only the reload handler, which never notifies the restart
   ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart);
   `docker/tasks/config.yml:49-86`). When dockerd picks the new settings up is NOT AVAILABLE (systemd behaviour).
3. **Docker is masked on Debian/Ubuntu during a run.** `docker/tasks/install.yml:15-30` symlinks
   `/etc/systemd/system/docker.service -> /dev/null` whenever that path does not exist at that point. The unit is
   unmasked by "Start and enable docker" (`docker/tasks/config.yml:113-119`), by the "Restart docker" handler when it
   runs
   (`docker/handlers/main.yml:14`), and earlier only by the recovery block `docker/tasks/install.yml:44-72` (after a
   package change with containers running). Whether that unmask removes the path again, so that every later run masks
   again, is NOT AVAILABLE (systemd behaviour). If the run fails or is interrupted in between (Docker package install,
   daemon.json, drop-in, CA file, handlers), **the unmask does not run** ([§2.3](#23-the-debianubuntu-mask-window)).
   NOT AVAILABLE: whether docker then starts at the next reboot.
4. **`/etc/hosts` lists every host.** The block loops over **all `groups['baremetal']` hosts**
   (`etc_hosts/tasks/etc-hosts.yml:25-41`),
   and it is the **first** thing the role does (`baremetal/tasks/main.yml:2-3`). So:
   (a) adding one host changes `/etc/hosts` on every host that bootstrap-servers runs on;
   (b) every baremetal host's facts are required: a baremetal host outside `bifrost` without gathered facts (for
   example unreachable during fact gathering, with no fact cache) makes `kolla_address` raise on **every** host
   (`kolla_ansible/kolla_address.py:84-91`), which fails the task on every host and ends the play for them before any
   other bootstrap task ([§3](#3-etchosts-generation)); (c) the per-run template work is O(N) per host, O(N²) in total.
5. **Fact gathering with `--limit` is serial per limited host.** With `--limit` covering L of N hosts, the second play
   of
   `gather-facts.yml` makes each limited host loop over about N/L other hosts **in sequence** (`gather-facts.yml:30-54`;
   loop items run one after another, ansible-core 2.14.18 `lib/ansible/executor/task_executor.py:287,335`). With
   `--limit one-compute` on a 1000-host inventory, one worker runs about 999 `setup` calls one after another.
   Fact caching avoids this; the tuning guide now documents filling the cache in parallel with `kolla-ansible
   gather-facts` (no limit) before a limited run (`doc/source/user/ansible-tuning.rst:36-85`).
6. **Re-running `bootstrap-servers` changes the host.** It disables ufw/firewalld (`baremetal/tasks/install.yml:3-32`,
   default
   `disable_firewall: True`, `baremetal/defaults/main.yml:31`), sets SELinux permissive
   (`baremetal/tasks/post-install.yml:21-28`,
   `baremetal/defaults/main.yml:26-28`), disables the libvirtd AppArmor profile on Ubuntu
   (`apparmor_libvirt/tasks/remove-profile.yml:12-22`),
   **removes host packages** (`packages/tasks/main.yml:15-23`, `packages/defaults/main.yml:24-33`): on Debian/Ubuntu
   `lxd`, `lxc`, `open-iscsi` and, with the libvirt container (default for kvm/qemu, `group_vars/all.yml:731`),
   `libvirt-bin`; on RedHat, with the libvirt container, `libvirt`, `libvirt-daemon`, `iscsi-initiator-utils`.
   `chrony` is no longer removed (the 2023.1 lists do not name it). It re-downloads the Docker apt key on every run
   (`docker/tasks/repo-Debian.yml:26-32`, `force: true`). None of this restarts containers, but it is not a no-op on a
   hardened production host.
7. **`kolla_serial` reaches only some commands.** The CLI injects `-e kolla_serial=${ANSIBLE_SERIAL}` **only for
   `upgrade` and
   `reconfigure`** (`tools/kolla-ansible:508,517`). It does this *after* user `-e` options, so a user
   `-e kolla_serial=30%` is
   **silently overridden to `0`** for those two commands. You must set the environment variable `ANSIBLE_SERIAL`. For
   `bootstrap-servers`, `deploy`, `prune-images` and the others, `-e kolla_serial=...` does work (as the docs suggest:
   `bootstrap-servers.rst:83`).
8. **CLI bugs.** `--ask-vault-pass` overwrites `VERBOSITY` with `$EXTRA_OPTS --ask-vault-pass`
   (`tools/kolla-ansible:385-388`).
   This drops earlier `-v` flags and duplicates the extra options given so far. `--include-dev` is declared as taking an
   argument
   (`include-dev:` at `:270`) but is handled as a flag (`:349-352`). `$CMD` is run unquoted (`:142`), so it is
   word-split and
   glob-expanded. New in 2023.1: without `-i`, **no inventory is passed at all** (`INVENTORY` set at `:279` is never
   used; only `-i` values are appended, `:588-590`), so ansible-core's default inventory source applies
   (`/etc/ansible/hosts` unless configured, ansible-core 2.14.18 `lib/ansible/config/base.yml:729-731`).
9. **No `ansible.cfg` is shipped for users.** The only ones are the CI template `tests/templates/ansible.cfg.j2` and a
   vagrant
   heredoc. The docs (only `doc/source/user/ansible-tuning.rst` now; the quickstart no longer has an `ansible.cfg`)
   recommend pipelining, `forks` (20 as an example), `gathering = smart` with jsonfile fact caching,
   `inject_facts_as_vars = False`, `kolla_ansible_setup_filter: "ansible_[!qt]*"` and
   `kolla_ansible_setup_gather_subset`.
   **They say nothing about ControlPersist, mitogen, strategy or `serial` for scale** (grep of `doc/source` is empty),
   although the CI template itself sets `ControlPersist=300` (`tests/templates/ansible.cfg.j2:10`).
10. **`destroy` acts on `hosts: all`, including the deploy host** (`localhost` is in `[deployment]`,
    `ansible/inventory/multinode:32-33`).
    `tools/cleanup-host` deletes **every** network namespace and every link whose line matches `tap`, `brq` or `vxlan`,
    and
    `rm -rf`s `/etc/kolla/*` except six names (`tools/cleanup-host:5-23,78-90`). `prune-images` prunes kolla-labelled
    images with `docker_prune` (`roles/prune-images/tasks/prune_images.yml:2-8`), a module that now comes from the
    `community.docker` collection, which is outside the sources; whether it removes only dangling images, so that old
    release tags are not reclaimed, is NOT AVAILABLE ([§7](#7-prune-images-ansibleprune-imagesyml-role-prune-images)).
11. **New in 2023.1: no `kolla` user by default.** `create_kolla_user` defaults to `False` in ansible-collection-kolla
    (`baremetal/defaults/main.yml:21`, `docker_sdk/defaults/main.yml:29`) and kolla-ansible does not override it (grep
    of `ansible/` is empty). So by default bootstrap-servers creates no `kolla` user, group, authorized key or sudoers
    file (`baremetal/tasks/post-install.yml:2-4`), and `/etc/kolla` is not chowned (`:9-16`). The kolla-ansible doc says
    the opposite ("which is ``true`` by default",
    `doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:107-108`).

---

## 1. `ansible/kolla-host.yml` (the `bootstrap-servers` command)

```yaml
# ansible/kolla-host.yml:1-10
- import_playbook: gather-facts.yml
- name: Apply role baremetal
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  roles:
    - { role: openstack.kolla.baremetal, tags: baremetal }
```

- FACT: the CLI maps `bootstrap-servers` to `kolla-host.yml` with `-e kolla_action=bootstrap-servers`
  (`tools/kolla-ansible:471-475`).
  The role is `openstack.kolla.baremetal` from ansible-collection-kolla, installed by `kolla-ansible install-deps`
  (`ansible-galaxy collection install -r requirements.yml --force`, `tools/kolla-ansible:131-138,429-432`) from the git
  branch named in `requirements.yml:2-5`. This sheet reads the `2023.1-eol` tag; what a later install of that branch
  contains is NOT AVAILABLE.
- FACT: the role no longer dispatches on `kolla_action`. `baremetal/tasks/main.yml:2-15` runs, in order: the `etc_hosts`
  role, `pre-install.yml`, `install.yml` (which imports the `packages` and `docker` roles,
  `baremetal/tasks/install.yml:34-38`),
  `post-install.yml` (which imports `kolla_user`, `docker_sdk` and `apparmor_libvirt`), then optionally
  `configure-ceph-for-zun.yml` (`zun_configure_for_cinder_ceph` and host in `zun-compute`).
- FACT: the target is `hosts: baremetal`, which in the sample inventories is control, network, compute, storage and
  monitoring
  (`ansible/inventory/multinode:35-40`). The deploy host (`[deployment]`) is **not** bootstrapped.
- FACT: there are no task-level tags inside the collection roles (grep of `tags:` in ansible-collection-kolla `roles/`
  is
  empty). `--tags` can only select `baremetal` plus the `always`-tagged gather-facts plays (`gather-facts.yml:22,54`).
  A subset of bootstrap tasks cannot be chosen with tags.
- FACT: the default `serial` is `"0"`, meaning one batch of all hosts. Parallelism is limited only by `--forks`.
- FACT: `kolla-host.yml` holds only the gather-facts import and this play. The Ussuri "Check CentOS variant" play no
  longer exists anywhere (grep for `kolla_centos_release` in `ansible/` is empty).
- CI coverage: `bootstrap-servers` runs **once, on fresh hosts** (`tests/setup_gate.sh:138`). Re-running it against a
  live
  deployment is **not exercised in CI**. The re-run hazards below are read from the code; runtime effects that the
  code does not show are marked NOT AVAILABLE.

### 1.1 Task-by-task: `pre-install.yml`

In 2023.1, `baremetal/tasks/pre-install.yml` holds a single task; the `/etc/hosts` work moved to the `etc_hosts` role,
which runs just before it, and the Docker repository tasks moved into the `docker` role, which runs during the
install phase ([§1.2](#12-task-by-task-installyml)).

| Lines | Task | Change made | Scale | Safe to re-run on a prod host with VMs? |
|---|---|---|---|---|
| `etc_hosts/tasks/etc-hosts.yml:2-10` | Ensure `127.0.0.1 localhost` (lineinfile, regexp `^127.0.0.1.*`, `create: true`, mode `0644`) | Replaces the **last** `127.0.0.1` line with exactly `127.0.0.1 localhost` | per host, O(1) | Yes. It may strip extra aliases from a hand-edited 127.0.0.1 line. |
| `etc-hosts.yml:18-23` | Remove `127.0.1.1 ... <hostname>` line | Deletes the Ubuntu-style hostname→127.0.1.1 mapping (RabbitMQ bug refs in comment, lines 12-17) | per host | Yes |
| `etc-hosts.yml:25-41` | **Generate /etc/hosts for all of the nodes** (blockinfile `# {mark} ANSIBLE GENERATED HOSTS`) | One line per **every host in `groups['baremetal']`**: `<api addr> <nodename> <hostname>` | **O(N) lines per host, O(N²) Jinja/hostvars work in total**. Needs facts of all N hosts. | Yes (no restart is attached). But see [§3](#3-etchosts-generation). |
| `etc-hosts.yml:47-60` | If `/etc/cloud/cloud.cfg` exists, write `/etc/cloud/cloud.cfg.d/99-kolla.cfg` = `manage_etc_hosts: false` (mode `0660`) | Stops cloud-init from rewriting /etc/hosts at boot | per host | Yes |
| `baremetal/tasks/pre-install.yml:2-9` | `net.ipv4.ping_group_range=0 2147483647` (RedHat only) into `kolla_sysctl_conf_path` (`/etc/sysctl.conf`, `group_vars/all.yml:605`) | `sysctl` is `ansible.posix.sysctl`: whether it reloads sysctl, and when, is NOT AVAILABLE | per host | Yes |

All four `etc_hosts` tasks run only when `customize_etc_hosts` (default `true`, `etc_hosts/defaults/main.yml:3`;
`etc_hosts/tasks/main.yml:2-4`). The `sudo` and `kolla` groups are now created by the `kolla_user` role, which runs only
when `create_kolla_user` is true (default `False`, [§1.3](#13-task-by-task-post-installyml)).

### 1.2 Task-by-task: `install.yml`

| Lines | Task | Notes, scale, re-run safety |
|---|---|---|
| `baremetal/tasks/install.yml:3-32` | **Firewall** (`when: disable_firewall`, default `True`, `baremetal/defaults/main.yml:31`): `ufw state=disabled policy=allow` (Debian, `ignore_errors`), `rpm -q firewalld`, then **stop and disable firewalld** (RedHat) | **Silently removes any host firewall an operator added since the last run.** Per host. Containers are not restarted. (`ufw` is `community.general.ufw`; its exact effect is NOT AVAILABLE.) |
| `packages/tasks/main.yml:2-13` | Install `ubuntu_pkg_install` (Debian family: `git`, `iputils-ping`, `sg3-utils-udev` if `enable_multipathd`, `tzdata`), `openeuler_pkg_install` (`python3-docker`) or `redhat_pkg_install` (`git`, `iputils`, `sudo`) (`packages/defaults/main.yml:10-22`), `state: present` | On Debian the apt cache is refreshed only when it is older than `apt_cache_valid_time`, 3600 s (`packages/defaults/main.yml:3`; ansible-core 2.14.18 `lib/ansible/modules/apt.py:1328-1336`). |
| `packages/tasks/main.yml:15-23` | **Remove packages** (`state: absent`): Debian family `lxd`, `lxc`, `open-iscsi`, plus `libvirt-bin` if `enable_nova_libvirt_container`; RedHat `libvirt`, `libvirt-daemon`, `iscsi-initiator-utils`, only if `enable_nova_libvirt_container` (`packages/defaults/main.yml:24-33`) | `enable_nova_libvirt_container` is true for `nova_compute_virt_type` kvm or qemu (`group_vars/all.yml:731`; default `kvm`, `:1031`). **A host that uses host-level iSCSI (for example boot-from-SAN, or a storage agent) loses `open-iscsi` (always on Debian/Ubuntu) or `iscsi-initiator-utils` (RedHat, with the libvirt container).** chrony is no longer in the lists. Re-running is a no-op only if the packages are already gone. |
| `docker/tasks/main.yml:2-3` → `repo-Debian.yml:2-49` | When `enable_docker_repo` (true except openEuler, `docker/defaults/main.yml:6`): `ca-certificates`, `gnupg` `state: present`; `/etc/apt/keyrings`; **Docker apt key downloaded with `force: true`** (26-32); optional apt pin from `docker_apt_package_pin` (34-43); apt repo `deb [signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/<distro> <release> stable` (`docker/defaults/main.yml:9-10`) | Needs network access to the Docker repo on every run (the key is fetched each time). |
| `docker/tasks/repo-RedHat.yml:2-27` | yum repo `docker` with `module_hotfixes: true` (9-20), rpm_key (22-27) | Repo config |
| `docker/tasks/install.yml:5-11` | `docker ps -f status=running -q` → `running_containers` | Snapshot taken before package changes |
| `docker/tasks/install.yml:16-19` | stat `/etc/systemd/system/docker.service` | `stat` does not follow symlinks by default (`follow` defaults to False, ansible-core 2.14.18 `lib/ansible/modules/stat.py:456,482-485`) |
| **`docker/tasks/install.yml:21-29`** | **Mask docker (symlink to /dev/null) on Debian/Ubuntu when that file does not exist** | Intended to stop apt from auto-starting docker before daemon.json exists (comment 13-14). It also fires on any re-run where the path is absent. Whether the unmask removes the symlink, so that **every re-run** masks again, is NOT AVAILABLE. See [§2.3](#23-the-debianubuntu-mask-window). |
| `docker/tasks/install.yml:32-39` | Install `docker_packages` with **`state: present`**, `update_cache: true` (apt with `cache_valid_time` 3600) | **An already-installed `docker-ce` is NOT upgraded** (`present`, not `latest`). List (`docker/defaults/main.yml:24-27`): `docker-ce` (or `docker-ce-<docker_yum_package_pin>` on RedHat, `docker` on openEuler, `:20`), `apparmor` on Debian, `iptables` only if `not docker_disable_default_iptables_rules` (default `"yes"`, so not installed). Whether a changed pin up- or downgrades an installed engine is NOT AVAILABLE (package manager behaviour). Doc: `bootstrap-servers.rst:62-65,90-93`. |
| `docker/tasks/install.yml:44-72` | If the install result changed **and** containers were running: `systemd docker started/enabled/unmasked`, wait for `docker info` (6×10 s), then `docker start <previously running IDs>` | Recovery path after a package change (comment at 2-3: an engine upgrade "may cause containers to stop"). What `docker start` does to containers that are still running is NOT AVAILABLE. |
| `docker/tasks/config.yml:1-119` | `/etc/docker`, **daemon.json** (notifies "Restart docker"), drop-in removal or template (notify "Reload docker service file"), registry CA (notifies "Restart docker"), **flush handlers** (110-111), start and enable docker (`masked: no`, 113-119) | See [§2](#2-docker-daemon-configuration-and-restart-the-exact-trigger). |
| `docker/tasks/main.yml:9-12` | Zun containerd config (only `containerd_configure_for_zun` and host in `zun-cni-daemon`) | See below |

### 1.3 Task-by-task: `post-install.yml`

| Lines | Task | Notes |
|---|---|---|
| `baremetal/tasks/post-install.yml:2-4` → `kolla_user/tasks/main.yml:2-10` | groups `docker`, `sudo`, `kolla_group` | Only when `create_kolla_user`, **default `False`** (`baremetal/defaults/main.yml:21`; not overridden in kolla-ansible) |
| `kolla_user/tasks/main.yml:12-21` | user `kolla` (group `kolla`, `groups: [docker, sudo]`, append) | Same condition |
| `kolla_user/tasks/main.yml:23-27` | `authorized_key` from `kolla_ssh_key.public_key` (passwords.yml) | Same condition. `authorized_key` is `ansible.posix.authorized_key`; whether an old key is removed when the key in passwords.yml is rotated is NOT AVAILABLE (no `exclusive` or `state` is passed) |
| `kolla_user/tasks/main.yml:29-38` | `/etc/sudoers.d/kolla-ansible-users`: `kolla ALL=(ALL) NOPASSWD: ALL`, mode `0640` | Same condition plus `create_kolla_user_sudoers` (default true, `kolla_user/defaults/main.yml:2`) |
| `post-install.yml:6-7` → `docker_sdk/tasks/main.yml:2-31` | Packages `python3-setuptools`, `python3-pip` (and `python3-docker` on Debian bookworm without virtualenv); `pip>19.3` into `virtualenv` if set; **Docker SDK** `docker>=3.0.0,<7.0.0` and `requests<2.32` via `pip3` or into the venv (`docker_sdk/defaults/main.yml:3-12`) | The pip step is skipped on bookworm without a virtualenv (`:31`). `state` defaults to present, so no change if matching versions are installed. Needs PyPI if not. Per host. The Ussuri recursive `chown` of the virtualenv is gone. |
| `post-install.yml:9-16` | `node_config_directory` (`/etc/kolla`), mode `0755`, owned by `kolla:kolla` only when `create_kolla_user` | |
| `post-install.yml:18-19` → `apparmor_libvirt/tasks/remove-profile.yml:2-22` | Ubuntu only, when `apparmor_remove_libvirt_profile` (= `enable_nova_libvirt_container`, `apparmor_libvirt/defaults/main.yml:6`; true by default through `group_vars/all.yml:731`): if `/etc/apparmor.d/usr.sbin.libvirtd` exists and `/etc/apparmor.d/disable/usr.sbin.libvirtd` does not, `apparmor_parser -v -R` the profile **and** link it into `disable/` | `changed_when: true`. The disable link makes the task skip on later runs, so it runs once per host. The Ussuri chronyd profile task is gone. |
| `post-install.yml:21-28` | `selinux: policy=targeted state={{ selinux_state }}` (default `permissive`, `change_selinux: True`, `baremetal/defaults/main.yml:26-28`) on RedHat | `selinux` is `ansible.posix.selinux`: whether it also changes the running mode is NOT AVAILABLE. No reboot is done by the role. |
| `post-install.yml:30-42` | global git `https.proxy` / `http.proxy` from `git_https_proxy` / `git_http_proxy` (default empty) | `community.general.git_config` |
| `baremetal/tasks/main.yml:11-15` → `configure-ceph-for-zun.yml:2-55` | Ceph apt/yum repo, EPEL on RedHat, `ceph-common` (only `zun_configure_for_cinder_ceph` and host in `zun-compute`) | Needs network access to `download.ceph.com` |

The Ussuri `enable_host_ntp` tasks (`ntpd -gq` on every run) no longer exist: no collection role names `ntp` (grep).
Time
sync is now only checked, by `prechecks` ([§5](#5-ansiblerolesprechecks-kolla-ansible-prechecks)).

`configure-containerd-for-zun.yml` (only `containerd_configure_for_zun` **and** host in `zun-cni-daemon`,
`docker/tasks/main.yml:9-12`):
it writes the CNI config and script and **overwrites `/etc/containerd/config.toml`** with only `[grpc] gid = ...`
(`docker/templates/containerd_config.toml.j2:1-2`). The CNI config and `config.toml` templates notify **"Restart
containerd"**
(`configure-containerd-for-zun.yml:11-20,38-45`; `docker/handlers/main.yml:17-21`). These tasks come after the
explicit flush in `config.yml`, so the containerd restart runs at the play's implicit flush after all roles, that is
after post-install (ansible-core 2.14.18 `lib/ansible/playbook/play.py:329-335`).
NOT AVAILABLE: whether container shims survive a containerd restart.

Kernel modules: the bootstrap roles load **none** (grep for `modprobe`/`module-load` in ansible-collection-kolla
`roles/`
is empty). Modules and sysctls are applied during `deploy`/`reconfigure` by `config-host.yml` in service roles: the
`module-load` role from `ironic`, `iscsi`, `loadbalancer`, `multipathd`, `neutron`, `nova-cell` and `openvswitch`, and
sysctls from `loadbalancer`, `neutron`, `nova-cell` and `opensearch` (grep of `roles/*/tasks/config-host.yml`).

---

## 2. Docker daemon configuration and restart: the exact trigger

### 2.1 What goes into `/etc/docker/daemon.json`

Base dict (`docker/vars/main.yml:2-5`): `log-opts: {max-file: docker_log_max_file, max-size: docker_log_max_size}`
(defaults `"5"` / `"50m"`, `group_vars/all.yml:113-114`). Keys merged in by `docker/tasks/config.yml:9-41`:

| Key | Source / condition | Default | Line (`config.yml`) |
|---|---|---|---|
| `cluster-store: etcd://<every etcd host>:<port>,...` (Zun) | `docker_configure_for_zun` **and** host in `zun-compute` | off (`all.yml:123`) | 33; value `group_vars/all.yml:125-126` loops over `groups['etcd']` |
| `insecure-registries: [docker_registry]` | `docker_registry_insecure` true. **It no longer follows `docker_registry`** | `"no"` (`all.yml:102`); `docker_registry: "quay.io"` (`all.yml:98`) | 12-14, 34 |
| `storage-driver` | `docker_storage_driver` non-empty | `""` (`docker/defaults/main.yml:29`) | 15-16, 35 |
| `data-root` | `docker_runtime_directory` non-empty | `""` (`all.yml:103`) | 17-18, 36 |
| `iptables: false` | `docker_disable_default_iptables_rules` | **`"yes"`** (`all.yml:108`) | 19-20, 37 |
| `bridge: none` | `docker_disable_default_network` | follows the previous (`all.yml:109`) | 21-22, 38 |
| `ip-forward: false` | `docker_disable_ip_forward` | follows the previous (`all.yml:110`) | 23-24, 39 |
| `default-ulimits: {nofile: 1048576/1048576}` | `docker_ulimit_nofile` | true on RedHat-family major version 9 (`docker/defaults/main.yml:47-49`) | 25-30, 40 |
| anything | `docker_custom_config` (dict) | `{}`; `{"exec-opts": ["native.umask=normal"]}` on openEuler (`docker/defaults/main.yml:30`) | 41 |

FACT: the file is rendered with Ansible's `to_nice_json`, which uses `sort_keys=True`
(ansible-core 2.14.18 `lib/ansible/plugins/filter/core.py:79-81`), so key order is stable and does not cause spurious
changes.
FACT: `copy content:` **overwrites the whole file**. Any key added by hand (for example `"live-restore": true` added
outside `docker_custom_config`) is **removed**, and that removal itself triggers a restart.
FACT: when `docker_registry_ca` is set, the CA is copied to `/etc/docker/certs.d/<docker_registry>/ca.crt` and a change
also notifies "Restart docker" (`config.yml:88-108`).

### 2.2 Why `docker_reloaded` never triggers a restart

There is no `docker_reloaded` register in 2023.1; its successor is the "Reload docker service file" handler, and the
reason it never leads to a restart is the same.

```python
# ansible-core 2.14.18 lib/ansible/modules/systemd.py:384-395
result = dict(name=unit, changed=False, status=dict())
# Run daemon-reload first, if requested
if module.params['daemon_reload'] and not module.check_mode:
    (rc, out, err) = module.run_command("%s daemon-reload" % (systemctl))
    if rc != 0: module.fail_json(...)
```
`changed` is set to True only by the `masked`, `enabled` and `state` branches (lines 475/521/553). The handler
"Reload docker service file" (`docker/handlers/main.yml:2-8`) passes only `name` and `daemon_reload`, so it always
reports unchanged, and its `notify: Restart docker` never fires: notifications are processed only for changed results
(ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:615-616`). Ansible 2.8 is not supported by 2023.1
(`tools/kolla-ansible:10-11`), so the Ussuri 2.8.20 comparison no longer applies.

**Conclusion (FACT for ansible-core 2.14.18):** during `bootstrap-servers`, the Docker daemon restarts **only** when the
write of daemon.json, or of the registry CA file, reports changed (rendered content differs from the file on disk, or
its mode differs; `lib/ansible/plugins/action/copy.py:285,342-380`, `lib/ansible/module_utils/basic.py:912,963`), and
only if the host reaches the flush at `docker/tasks/config.yml:110-111`. Triggers:
- first bootstrap of a host (the file does not exist yet), or any hand-edited daemon.json;
- the first 2023.1 run on a host whose daemon.json was rendered with other defaults (for example `iptables`, `bridge`,
  `ip-forward`, now on by default, `group_vars/all.yml:108-110`; `default-ulimits` on EL9);
- changing `docker_registry_insecure` (and `docker_registry` while it is true), `docker_log_max_file`,
  `docker_log_max_size`, `docker_storage_driver`, `docker_runtime_directory`, `docker_disable_default_iptables_rules`,
  `docker_disable_default_network`, `docker_disable_ip_forward`, `docker_ulimit_nofile*` or `docker_custom_config`;
- with `docker_registry_ca` set: a changed CA file, or a changed `docker_registry` (new destination path);
- on **Zun compute hosts** with `docker_configure_for_zun`: **adding or removing an etcd host** (changes
  `cluster-store`);
- a **package change** does not notify the handler by itself. What a docker-ce package upgrade does to the daemon
  is NOT AVAILABLE; the role's comment says it "may cause containers to stop" (`docker/tasks/install.yml:2-3`). Kolla
  then runs
  `docker start` on previously running containers (`docker/tasks/install.yml:44-72`).

With `docker_systemd_reload: true` the handler reloads instead of restarting (`docker/handlers/main.yml:13`); which
daemon.json changes dockerd applies on a reload is NOT AVAILABLE (Docker behaviour).

**Not** triggers (latent changes): adding, changing or removing `docker_http_proxy`, `docker_https_proxy`,
`docker_no_proxy`, or the Zun `docker_zun_options` drop-in (`docker/tasks/config.yml:49-86`). These are written to disk
and daemon-reloaded, and no Kolla task restarts Docker for them. When dockerd picks them up is NOT AVAILABLE (systemd
behaviour). Also latent: a daemon.json change on a host that failed before the flush
([§0 item 1](#0-most-important-findings)).
NOT AVAILABLE: whether dockerd refuses to start if the same option ends up both as a dockerd flag in the drop-in and in
daemon.json.

### 2.3 The Debian/Ubuntu mask window

Sequence per run on Debian/Ubuntu (FACT):
`docker/tasks/install.yml:21-29` mask (the symlink is created when the path is absent), then the Docker package install
(`:32-39`), then daemon.json, drop-in and CA tasks (`docker/tasks/config.yml:9-108`), then the handler flush
(`:110-111`; "Restart docker" carries `masked: no` when notified), then `config.yml:113-119` `masked: no`, which runs
`systemctl unmask docker` when systemd reports the unit as masked (ansible-core 2.14.18
`lib/ansible/modules/systemd.py:468-482`). The recovery block `docker/tasks/install.yml:44-72` also sets `masked: no`
(line 52), but only when the package install changed and containers were running. Pip installs, user creation and the
AppArmor and SELinux tasks now come after the unmask (`baremetal/tasks/main.yml:7-9`).
FACT: a failure or interruption between those points, unless it comes after the recovery block or the handler has
run, leaves the symlink in place. The roles have no `rescue` or `always` (grep of ansible-collection-kolla `roles/` is
empty), and a failed host runs no further task of the play (ansible-core 2.14.18
`lib/ansible/executor/play_iterator.py:468-478`).
NOT AVAILABLE: whether the running daemon is affected, and whether **Docker, and therefore every Kolla container and VM
on that host, starts after the next reboot**. One related statement in the sources is the Ansible systemd
module's note that "a masked unit is impossible to start" (ansible-core 2.14.18 `lib/ansible/modules/systemd.py:43`).
Also NOT AVAILABLE: whether `systemctl unmask` removes the symlink, which decides whether the next run masks again.
Check after any failed run: `ls -l /etc/systemd/system/docker.service` should **not** point to `/dev/null`.

### 2.4 Blast radius of a restart

- FACT: the restart is the "Restart docker" handler, run at `docker/tasks/config.yml:110-111` on every notified host of
  the current batch. With default `serial: 0`, **all baremetal hosts whose daemon.json changed restart Docker in the
  same
  step** (subject to forks). That includes all controllers at once.
- FACT: in 2023.1 `kolla_docker` gives containers no Docker restart policy (in `module_utils/kolla_docker_worker.py`
  `restart_policy` appears only in the one-shot checks at `:359,402,471`). Each container runs under a systemd unit
  `kolla-<name>-container.service` with `Wants=docker.service`, `After=docker.service`,
  `ExecStart=/usr/bin/docker start -a <name>`, `ExecStop=/usr/bin/docker stop <name> -t <graceful_timeout>` and
  `Restart=always` for `unless-stopped` (`module_utils/kolla_systemd_worker.py:20-40,51-53`; `docker_restart_policy`,
  `group_vars/all.yml:117`). NOT AVAILABLE: whether those units bring the containers back after the daemon restarts
  (systemd and Docker behaviour). FACT: `kolla_docker` sets no container `StopTimeout` (grep for
  `stop_timeout|StopTimeout` in `library/kolla_docker.py` and `module_utils/` is empty). `docker_graceful_timeout: 60`
  (`all.yml:140`) is used by the unit's `ExecStop` and by `kolla_docker` stops
  (`module_utils/kolla_docker_worker.py:438-450`),
  not by the daemon. NOT AVAILABLE: the stop timeout Docker applies to containers on a daemon restart.
- NOT AVAILABLE: whether restarting Docker on all MariaDB hosts at once stops the whole Galera cluster. FACT: the kolla
  image has no recovery logic for it. On a normal start the container runs `mysqld_safe` (plus `BOOTSTRAP_ARGS` only if
  set) with every MariaDB host of the shard in `gcomm://`, and the image's start path has no `grastate.dat` or
  `safe_to_bootstrap` handling and no new-cluster decision (kolla `docker/mariadb/mariadb-server/extend_start.sh:31-61`;
  `roles/mariadb/templates/galera.cnf.j2:29`;
  [Kolla images §5.4](../../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)). NOT AVAILABLE: whether
  Galera re-forms the cluster by itself or `kolla-ansible mariadb_recovery` is needed. With a single MariaDB host in the
  shard, `gcomm://` is empty (`galera.cnf.j2:29`); whether that host comes back without recovery is NOT AVAILABLE.
- Compute nodes: `nova_libvirt` runs with `pid_mode: host`, `cgroupns_mode: host` and bind-mounts `/sys/fs/cgroup`
  (`roles/nova-cell/defaults/main.yml:8-9,369-376`). NOT AVAILABLE: whether running QEMU processes survive the container
  restart; the sources do not show whether the guests sit in machined slices or in the container cgroup. Note
  `tools/cleanup-containers:31-37`: "Container engine ($engine) will not be able to stop the nova_libvirt container
  with those [qemu processes] running".
- **Optional unit hazard:** `tools/setup-compute-libvirt.yml` (not run by any kolla-ansible command) installs
  `kolla-libvirt-guests-<engine>.service` (`:10,15-16`). The docker variant has `Requires=docker.service`, and its
  `ExecStop` stops nova_compute and runs `libvirt-guests.sh shutdown`
  (`tools/kolla-libvirt-guests-docker.service:6,18-19`).
  NOT AVAILABLE: whether systemd propagates a restart of `docker.service` to units that `Requires=` it, and so whether,
  on hosts where an operator installed this unit, **a Docker restart shuts down or managed-saves every guest**.
- Documented mitigations (`doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:55-89`): `--limit`
  batches
  keeping quorum, `-e kolla_serial=30%`, or Docker `live-restore` ("issues reported ... use it at your own risk"). The
  way to
  set live-restore in a supported way is `docker_custom_config: {"live-restore": true}`. FACT: adding it changes the
  rendered daemon.json, so that run restarts Docker ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)); if the
  file on disk already matches the rendered content, the handler is not notified. NOT AVAILABLE: whether containers
  survive that first restart, and whether pre-seeding daemon.json by hand and running `systemctl reload docker` before
  bootstrap-servers activates live-restore.
- Interaction with `config_strategy: COPY_ALWAYS` (`all.yml:43`, passed as `KOLLA_CONFIG_STRATEGY` in
  `docker_common_options`, `all.yml:148-149`). FACT (kolla image): every Kolla service container except `bifrost_deploy`
  (which runs `/sbin/init`, kolla `docker/bifrost/bifrost-deploy/Dockerfile.j2:29-30`) runs `kolla_set_configs` when it
  starts, and under `COPY_ALWAYS` that re-copies the files listed in its `config.json` from `/etc/kolla/<svc>/` and
  rewrites `/run_command` (kolla `docker/base/start.sh:11`, `docker/base/set_configs.py:300-319,535-541`; [Kolla images
  §2](../../concepts/kolla-images.md#2-start-path-common-to-every-image)). A container that starts again after a Docker
  restart therefore **activates any config that was rendered but not yet applied**, for example by
  `kolla-ansible genconfig` (`tools/kolla-ansible:540-543`) or a failed reconfigure. Removals are not applied:
  destinations of entries dropped from `config.json`, or of optional sources that are gone, stay in the container
  ([Kolla images §3.5](../../concepts/kolla-images.md#35-what-a-restart-applies)).

---

## 3. `/etc/hosts` generation

```jinja
# ansible-collection-kolla roles/etc_hosts/tasks/etc-hosts.yml:30-36
{% for host in groups['baremetal'] %}
{% set api_interface = (hostvars[host]['api_interface'] | replace('-', '_')) %}
{% if host not in groups['bifrost'] or api_interface in hostvars[host].ansible_facts %}
{% set hostnames = [hostvars[host].ansible_facts.nodename, hostvars[host].ansible_facts.hostname] %}
{{ 'api' | kolla_address(host) }} {{ hostnames | unique | join(' ') }}
```
- FACT: **it loops over all baremetal hosts**. Adding a host changes the managed block on **every** host
  bootstrap-servers runs
  against. No handler or restart is attached, so a change restarts nothing by itself.
- FACT: it needs facts for **all** baremetal hosts. `kolla_address` raises
  `FilterError("Interface ... not present on host ...")`
  when `hostvars[host]['ansible_facts']` lacks the interface (`kolla_ansible/kolla_address.py:84-91`). A host whose
  facts were never gathered (for example unreachable during fact gathering, with no fact cache) has an empty
  `ansible_facts` (ansible-core 2.14.18 `lib/ansible/vars/manager.py:307-308`, `lib/ansible/vars/clean.py:162-171`). So
  **one fact-less baremetal host outside `bifrost` fails this task on every host**: `FilterError` is an
  `AnsibleFilterError` (`kolla_ansible/exception.py:23`), and an `AnsibleError` fails the task (ansible-core 2.14.18
  `lib/ansible/executor/task_executor.py:190-191`). Those hosts then run no further task of the play
  (`lib/ansible/executor/play_iterator.py:468-478`), and since `etc_hosts` runs first (`baremetal/tasks/main.yml:2-3`),
  no bootstrap task runs at all. In practice every baremetal host must be reachable, or have cached facts, for
  bootstrap-servers.
- The Ussuri minor bug is fixed: the template now applies the same `-`→`_` replacement as the `when:` clause
  (`etc-hosts.yml:31,41`).
- With `--limit new-hosts`, only the limited hosts get the full list. **Existing hosts never learn the new names.** The
  docs
  require including all controllers in the limit for RabbitMQ (`doc/source/user/adding-and-removing-hosts.rst:22-29`).
  For
  computes, without `libvirt_tls` the libvirt connection and migration addresses are IPs
  (`nova.conf.d/libvirt.conf.j2:7-8`). **Exception:** with
  `libvirt_tls`, `live_migration_inbound_addr = migration_hostname = ansible_facts.nodename`
  (`roles/nova-cell/templates/nova.conf.d/libvirt.conf.j2:2-5`, `roles/nova-cell/defaults/main.yml:554`). NOT AVAILABLE:
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
# gather-facts.yml:5-22 (play 1, hosts: all, serial: kolla_serial)
- group_by: key: "all_using_limit_{{ (ansible_play_batch | length) != (groups['all'] | length) }}"
- setup: {filter: kolla_ansible_setup_filter, gather_subset: kolla_ansible_setup_gather_subset}
  when: not ansible_facts
# gather-facts.yml:30-54 (play 2, hosts: all_using_limit_True)
vars:
  batch_index: "{{ ansible_play_batch.index(inventory_hostname) }}"
  batch_size: "{{ ansible_play_batch | length }}"
  delegate_hosts: "{{ groups['all'][batch_index | int::batch_size | int] }}"
setup: ... delegate_facts: True, delegate_to: "{{ item }}", with_items: "{{ delegate_hosts }}"
when: [item not in groups["all_using_limit_True"], not hostvars[item].ansible_facts]
```
Cost model, with N = |groups['all']| (this **includes `localhost`** from `[deployment]`) and L = hosts selected by
`--limit`:
- **No limit, serial 0:** play 1 runs N `setup` calls in parallel (forks). Play 2 is empty.
- **`--limit` with L hosts:** play 1 runs L parallel `setup` calls. Play 2 runs on the same L hosts. Limited host *i*
  loops
  **sequentially** over `groups['all'][i::L]`, about N/L items, each a delegated `setup` (SSH from the deploy host to
  the
  *item* host, facts stored on the item); items that are themselves limited hosts are skipped (`gather-facts.yml:51`).
  The items of one host's loop run one after another (ansible-core 2.14.18
  `lib/ansible/executor/task_executor.py:287,335`). Total is N−L delegated setups, but only **L run at the same time**.
  The resulting wall time is NOT AVAILABLE. **L=1 means fully serial fact gathering of the whole inventory.**
- **With `kolla_serial` (no limit):** each batch is smaller than N, so every host joins `all_using_limit_True`, and
  every item of play 2 is then skipped by `item not in groups["all_using_limit_True"]` (loop evaluation only, no SSH).
- **With fact caching** (`gathering = smart` + `fact_caching`, `ansible-tuning.rst:36-66`): `when: not ansible_facts` is
  false
  for cached hosts, so both plays skip `setup`. The guide now also documents populating the cache with
  `kolla-ansible gather-facts` without a limit before a limited command (`ansible-tuning.rst:68-85`;
  `tools/kolla-ansible:494-497`). This is the only documented way to make `--limit` runs cheap at scale. Stale-cache
  risk: IP or interface changes will not be seen until the cache expires (`fact_caching_timeout`).
- FACT: an unreachable *other* host without cached facts makes its delegated item in play 2 return `unreachable`
  (ansible-core 2.14.18 `lib/ansible/executor/task_executor.py:636-637`). One unreachable item makes the whole task
  result
  unreachable (`lib/ansible/executor/task_result.py:72-73,96-106`), so the **limited** host is marked unreachable and
  removed from the play (`lib/ansible/plugins/strategy/__init__.py:589-595`) and from every later play
  (`strategy/__init__.py:312-315`, `lib/ansible/executor/playbook_executor.py:174,217`). So `--limit newnode` can fail
  because an unrelated node is down.
- FACT: `kolla_ansible_setup_filter` and `kolla_ansible_setup_gather_subset` apply **only** in `gather-facts.yml`.
  Playbooks that do
  not import it (`destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, and `certificates.yml`
  when
  none of `kolla_enable_tls_backend`, `rabbitmq_enable_tls`, `certificates_generate_libvirt` is true,
  `certificates.yml:2-5`)
  use implicit full play-level fact gathering.
- FACT: the documented filter `"ansible_[!qt]*"` (`ansible-tuning.rst:119`, aimed at "virtual interfaces beginning with
  q
  or t", :114-115) also hides real interfaces whose names start with `q` or `t` (for example `team0`, `trunk0`, `tun0`).
  `setup` keeps only the `ansible_`-prefixed fact names that match the filter, and each interface's facts sit under its
  name
  (ansible-core 2.14.18 `lib/ansible/modules/setup.py:196,210-216`,
  `lib/ansible/module_utils/facts/ansible_collector.py:58-76`,
  `lib/ansible/module_utils/facts/network/linux.py:56-57`). `kolla_address` then fails for `api_interface`,
  `tunnel_interface` and so on if they are named that way (`kolla_ansible/kolla_address.py:84-91`).

---

## 5. `ansible/roles/prechecks` (`kolla-ansible prechecks`)

- FACT: `prechecks` runs `site.yml` with `-e kolla_action=precheck` (`tools/kolla-ansible:433-436`). The common
  `prechecks` role
  runs on `hosts: kolla_action_precheck`, which is **all** hosts (`site.yml:79-84`). Each service play then runs its own
  `<role>/tasks/precheck.yml` (59 files, about 3.2k lines in total).
- The common role (`roles/prechecks/tasks/main.yml:1-23`) checks:
  - inventory: the `loadbalancer` group exists and is non-empty when `enable_loadbalancer` (`inventory_checks.yml`).
  - host OS (`host_os_checks.yml`): CentOS Stream 9, Debian bullseye or bookworm, openEuler 22.03, Rocky 9, Ubuntu jammy
    (`vars/main.yml:11-22`); CentOS Linux (non-Stream) fails. Can be skipped with
    `prechecks_enable_host_os_checks: false`.
  - **time sync** (new, skipped for `deployment` hosts): one of chrony, chronyd, ntp, ntpd or systemd-timesyncd must be
    active, and `timedatectl status` must say `synchronized: yes` (`timesync_checks.yml:2-47`). Can be skipped with
    `prechecks_enable_host_ntp_checks: false` (`defaults/main.yml:6`).
  - `/etc/localtime` exists, plus `/etc/timezone` on Debian (`datetime_checks.yml`).
  - `api_interface` present, active, with an address (`port_checks.yml`; skipped for `deployment` group hosts,
    `main.yml:13-15`).
  - systemd is the service manager (`service_checks.yml:2-7`); `docker --version` ≥ 18.09 (`service_checks.yml:9-17`,
    `vars/main.yml:2`); Docker SDK ≥ 3.4.1 and `dbus` importable (baremetal only) and Ansible 2.13–2.14
    (`package_checks.yml:2-32`, `vars/main.yml:3-5`).
  - empty values in passwords.yml (`grep`, `delegate_to: localhost`, `run_once`) (`service_checks.yml:19-30`; passes
    vacuously
    if the vault is encrypted, per the note at 19-21).
  - fails if `nscd` is running (`service_checks.yml:32-46`).
  - TLS VIP consistency, `enable_ceph` removed, and RabbitMQ HA vs quorum-queue settings (`service_checks.yml:48-71`).
  - `config_owner_user` and group exist; passwordless sudo works (`user_checks.yml`).
  - external DB reachable when `enable_mariadb` is false (`database_checks.yml`).
- Service prechecks use `kolla_container_facts`, `wait_for ... state: stopped timeout: 1` port checks (skipped when the
  owning
  container already exists, for example `roles/nova-cell/tasks/precheck.yml:8-19,31-45`), `stat`, `getent`, `vgs`,
  `ping` of the VIP,
  `ip addr`, a read-only HAProxy `show stat` via `docker exec` (`roles/loadbalancer/tasks/precheck.yml:204-210`), and
  read-only `rabbitmqctl list_policies`/`list_queues` via `docker exec` (`roles/rabbitmq/tasks/precheck.yml:198-240`).
- **Does it change anything?** FACT: no module that modifies state was found. Every `command`/`shell` read is
  `changed_when: false` or read-only, and there are no `template`/`copy`/`file`/`kolla_docker`/`lineinfile`/`sysctl`/
  `service`/`systemd` tasks in the precheck files (grep). It is **safe on a running production cloud**.
- **Cost:** O(1) tasks per host per enabled service, plus full `gather-facts.yml`. Loops over other hosts exist only for
  `rabbitmq`/`outward-rabbitmq` hostname resolution (`roles/rabbitmq/tasks/precheck.yml:62-78,152-172`, for the rabbitmq
  hosts only) and the external-database check (`database_checks.yml:7`). There is no N² behaviour. The dominant cost
  at scale is Ansible's per-task overhead across about 80 plays (56 in `site.yml` plus 23 imported from
  `gather-facts.yml`, `mariadb.yml`, `rabbitmq.yml`, `nova.yml`). Prechecks plays inherit `serial: kolla_serial` from
  site.yml where it is set.

---

## 6. `destroy` (`ansible/destroy.yml`, role `destroy`, `tools/cleanup-*`)

```yaml
# ansible/destroy.yml:1-5
- name: Apply role destroy
  hosts: all          # includes localhost/[deployment] in the sample multinode inventory
  roles: [destroy]    # no serial, implicit gather_facts, no gather-facts.yml import
```
- CLI: needs `--yes-i-really-really-mean-it` spelled in full (`tools/kolla-ansible:452-470`; `RAW_ARGS` check at
  336-342).
  `--include-images` sets `destroy_include_images=yes`. `--include-dev` sets `destroy_include_dev=yes`, **but see the
  bug in [§11](#11-toolskolla-ansible-cli)**.
- Role flow (`roles/destroy/tasks/main.yml:1-8`): `validate-docker-execute.sh` (`sudo $CONTAINER_ENGINE ps`), then
  `cleanup-containers <engine>`, then `cleanup-images --all -e <engine>` (only if `destroy_include_images`, default
  `enable_destroy_images: "no"`, `all.yml:775`), then `cleanup-host` (`become: true`, env vars passed in
  `cleanup_host.yml:5-16`) and, for Octavia health-manager hosts with auto-configured tenant networking, removal of the
  `octavia-interface` service and dhclient config (`cleanup_host.yml:18-39`). The role ignores `kolla_action` and has no
  tags.
- `tools/cleanup-containers`:
  - Safety guard (31-37): **aborts if `nova_libvirt` is running and non-Xen-dom0 qemu processes exist**.
  - If `openvswitch_vswitchd` is among the containers and `neutron_openvswitch_agent` is running: `neutron-ovs-cleanup
    --ovs_all_ports`, then **delete every OVS bridge** (50-56). NOT AVAILABLE: whether the `exec -it` at line 55 fails
    without a TTY under Ansible's `script`, and so whether bridges survive.
  - Stops every **kolla-labelled container** through its systemd unit (`systemctl stop kolla-<name>-container.service`,
    59-61), `rm -v -f`s them (64), disconnects them from the host network (66-69), then `volume rm` **every volume
    mounted
    by them** (44-47, 72). That includes `mariadb`, `rabbitmq`, `nova_compute` (instance disks when the default volume
    is
    used), `libvirtd`, `kolla_logs` and so on. It also removes the `/var/log/kolla` link (75) and every
    `/etc/systemd/system/kolla-*-container.service` unit file (77-79).
- `tools/cleanup-host`:
  - **Deletes ALL network namespaces** (`ip netns list`, 5-8). This is not limited to kolla's. NOT AVAILABLE: whether
    `ip netns list` prints lines of the form `name (id: N)`; the unquoted `$line` (line 7) would pass those extra
    words to `ip netns delete`.
  - Deletes every link whose `ip -o link` line matches `/tap/`, `/brq/` or `/vxlan/` (10-23).
  - Removes the VIPs from interfaces when `enable_haproxy == yes` (27-35).
  - Copies `/etc/fstab` to `/etc/fstab_backup` (37-38), then for Swift:
    `cat /etc/fstab | grep "/srv/node/d*" | xargs umount`
    (42). This **feeds whole fstab lines to umount** (bug), then deletes those fstab lines (43).
  - `rm -rfv` of custom datadirs when they differ from the default volume names (46-69): glance, nova_compute, gnocchi,
    influxdb, opensearch. For example `nova_instance_datadir_volume` set to a host path means **instance storage is
    wiped**.
  - Runs the OVS-DPDK uninstall script if present (71-76).
  - **`rm -rfv /etc/kolla/*` except `passwords.yml`, `globals.yml`, `globals.d`, `kolla-build.conf`, `config`,
    `certificates`**
    (78-90). The path is hard-coded (`FOLDER_PATH="/etc/kolla"`, 71) and ignores `node_config_directory`. Because
    `localhost` is in `hosts: all`, this also runs on the **deploy host** unless `--limit` excludes it, which deletes
    `admin-openrc.sh`, `clouds.yaml` and anything else stored under `/etc/kolla`.
- `tools/cleanup-images`: the Ussuri Python 2 line is fixed (`python3`, line 6). `--all` runs `rmi -f` on every
  kolla-labelled image (60-63, 94).
- Scale and safety: per host, all hosts in parallel (forks), **no serial and no batch protection**. Never run it on
  production
  without `--limit`. For decommissioning, the docs use `stop` plus inventory removal, **not** `destroy`
  (`doc/source/user/adding-and-removing-hosts.rst:140-172,200-224`).
- CI: no 2023.1 CI job runs `destroy` (grep of `tests/*.sh` and `tests/*.yml`).

## 7. `prune-images` (`ansible/prune-images.yml`, role `prune-images`)

```yaml
# ansible/prune-images.yml:1-9
- import_playbook: gather-facts.yml
- name: Apply role prune-images
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  roles: [prune-images]
# roles/prune-images/tasks/main.yml:2-4: validate_docker_execute.yml, then prune_images.yml
# roles/prune-images/tasks/prune_images.yml:2-8
docker_prune: {images: yes, images_filters: {label: kolla_version}, timeout: "{{ docker_image_prune_timeout }}"}  # default 300
```
- CLI needs `--yes-i-really-really-mean-it` (`tools/kolla-ansible:548-559`); the docs call it pruning "orphaned Docker
  images" (`doc/source/user/operating-kolla.rst:267-268`).
- FACT: `docker_prune` is no longer an ansible-core module; ansible-core redirects it to `community.docker.docker_prune`
  (ansible-core 2.14.18 `lib/ansible/config/ansible_builtin_runtime.yml:745-746`). That collection is not in the
  sources, and neither kolla-ansible (`requirements.yml`) nor ansible-collection-kolla (`galaxy.yml`,
  `dependencies: {}`)
  declares it. NOT AVAILABLE: whether `images: yes` removes only dangling images (as the Ussuri module did), and so
  whether **old-release images (for example `zed` after an upgrade to `2023.1`) are kept**. To remove images of an old
  release explicitly, `tools/cleanup-images --image-version <value>` removes images whose `kolla_version` label equals
  that value (`tools/cleanup-images:75-77,94`); what value the images carry is NOT AVAILABLE here. Manual `docker rmi`
  also works.
- NOT AVAILABLE: whether Docker would prune an image that a container uses (Docker behaviour). Cost is one Docker API
  call per host, plus the full `gather-facts.yml` (which is not needed by the role, but is imported and pays the --limit
  fact cost from [§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)).
- CI: not covered (grep of `tests/`).

## 8. `post-deploy` (`ansible/post-deploy.yml`)

- Two plays on `hosts: localhost`, implicit fact gathering, tasks with `become: true` (`post-deploy.yml:1-38`):
  - creates `/etc/openstack` (mode `0700`, owned by the invoking user) and templates
    `roles/common/templates/clouds.yaml.j2`
    to `{{ node_config }}/clouds.yaml`, mode `0600` (`:2-21`). Note the file goes to `node_config`, not to
    `/etc/openstack`.
  - templates `roles/common/templates/admin-openrc.sh.j2` to `{{ node_config }}/admin-openrc.sh`, owned by the invoking
    user's uid/gid, mode `0600` (`:23-33`), and, with `enable_octavia`, the Octavia openrc (`:35-38`).
  `node_config` = `CONFIG_DIR`, default `/etc/kolla` (`all.yml:10`).
- Contents: `OS_PASSWORD={{ keystone_admin_password }}` in plaintext, `OS_AUTH_URL={{ keystone_internal_url }}` (the
  **internal** endpoint; `keystone_admin_url` is now the same URL, `all.yml:864-865`), `OS_INTERFACE=internal`, and
  optional `OS_CACERT` from `kolla_admin_openrc_cacert` (`admin-openrc.sh.j2:1-25`). `clouds.yaml` holds two clouds,
  `kolla-admin` (public Keystone URL) and `kolla-admin-internal`, both with the admin password in plaintext
  (`clouds.yaml.j2:1-26`).
- No `kolla_action` is passed (`tools/kolla-ansible:498-501`). Cost is O(1) and it is safe to re-run. **`destroy`
  deletes both
  files on the deploy host** ([§6](#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)).

## 9. `mariadb_backup.yml` and `mariadb_recovery.yml` (playbook level only)

```yaml
# ansible/mariadb_backup.yml:1-7
- name: Backup MariaDB
  hosts: mariadb
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariabackup | bool }]
# ansible/mariadb_recovery.yml:1-9
- name: Recover mariadb
  hosts: mariadb
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariadb | bool }]
  vars: { mariadb_recover: true }
```
- CLI: `mariadb_backup` passes `-e kolla_action=backup -e mariadb_backup_type={full|incremental}`. `mariadb_recovery`
  passes `-e kolla_action=deploy` (`tools/kolla-ansible:437-446`). The Ussuri `-e common_run=true` is gone (grep for
  `common_run` in kolla-ansible is empty): `common` is its own play in `site.yml` (`site.yml:86-97`), and these two
  playbooks hold only the mariadb play, so `common` does not run.
- Neither playbook imports `gather-facts.yml`, and neither has `serial`. Implicit full fact gathering covers the
  **mariadb hosts only**.
- Backup runs only on `mariadb_backup_host` = `groups[mariadb_shard_group][0]` (`roles/mariadb/defaults/main.yml:123`,
  `group_vars/all.yml:398`), and only where `mariadb_backup_possible` (`roles/mariadb/defaults/main.yml:127`;
  `roles/mariadb/tasks/backup.yml:33-35`). It requires `enable_mariabackup: yes` (default `no`, `all.yml:709`).
  Otherwise every task is skipped silently.
- **Image-tag pitfall:** no longer applies in 2023.1. The backup container uses the image of the running `mariadb`
  container, or the configured mariadb image (`roles/mariadb/tasks/backup.yml:18-21`), and `openstack_tag` no longer
  depends on facts registered only in `site.yml` (`group_vars/all.yml:580-581`; grep for `kolla_centos_release` is
  empty).
- CI: `mariadb_recovery` is tested with `--tags mariadb --skip-tags common` (`tests/test-mariadb.sh:21-25`).
  `mariadb_backup` is
  not tested in CI (grep of `tests/`).

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
- It runs on the deploy host only. Facts of all hosts are needed for the backend certificate's SAN list, which loops
  over
  `groups['tls-backend']` with `kolla_address` (`roles/certificates/templates/openssl-kolla-backend.cnf.j2:16-17`).
- FACT: every openssl step is guarded with `creates:` (for example `generate-backend.yml:21,32,48`;
  `generate.yml:28,39,55,98,109,125`),
  so re-runs never regenerate. **FACT:** after adding a `tls-backend` (controller) host, the backend cert keeps its old
  SANs until `backend.csr`/`backend.crt` are deleted by hand. The SAN config is re-templated
  (`generate-backend.yml:8-14`), but the CSR and certificate steps are skipped while those files exist (`:23-32,34-48`;
  the `command` module exits without running when the `creates` path exists, ansible-core 2.14.18
  `lib/ansible/modules/command.py:298-313`). The CLI marks this command "For Development Only"
  (`tools/kolla-ansible:200`).

---

## 11. `tools/kolla-ansible` CLI

- **`--tags`, `--skip-tags`, `--limit`, `--forks`, `-e`, `--vault-*`, and now `--check`/`-C` and `--diff`/`-D`** are
  global
  options appended to `EXTRA_OPTS` (`tools/kolla-ansible:306-324,354-393`), so **every subcommand accepts `--tags`**.
  Whether they mean anything depends on the playbook: `kolla-host.yml` only has the `baremetal` tag, and
  `destroy`/`prune-images`/`post-deploy` have no role tags. The extra environment variable `EXTRA_OPTS` is honoured
  (`:282`).
- **Inventory:** `-i` may be given several times (`:296-299`); each value is appended as `--inventory` (`:588-590`).
  Without `-i`, no inventory is passed: the default `INVENTORY` set at `:279` is never used, and ansible-core falls back
  to
  its configured default (`/etc/ansible/hosts` unless configured, ansible-core 2.14.18
  `lib/ansible/config/base.yml:729-731`).
- **`kolla_serial`:** `ANSIBLE_SERIAL=${ANSIBLE_SERIAL:-0}` (`:288-290`, comment: "Serial is not recommended and
  disabled by
  default"). It is passed **only** by `upgrade` (`:508`) and `reconfigure` (`:517`) as
  `-e kolla_serial=${ANSIBLE_SERIAL}`.
  Because that `-e` is appended **after** the user's `--extra` options, Ansible's last-wins rule for extra-vars
  (ansible-core 2.14.18 `lib/ansible/utils/vars.py:183-204`) means
  **`kolla-ansible reconfigure -e kolla_serial=1` silently runs with `0`**. Use
  `ANSIBLE_SERIAL=1 kolla-ansible reconfigure`.
  `kolla-ansible upgrade -e kolla_serial=1` is overridden the same way (`:508`); use `ANSIBLE_SERIAL=1` there too.
  For every other command, `-e kolla_serial=...` works. Plays that **ignore** `kolla_serial` are listed below.
  - `site.yml`: "Group hosts based on configuration", prechecks, and cyborg, whose play reads
    `serial: '{{ serial|default("0") }}'` (`site.yml:784`). In the imported `mariadb.yml` and `rabbitmq.yml`, the
    restart plays use a fixed `serial: "33%"` (`mariadb.yml:20,34`, `rabbitmq.yml:32,88`) and the other plays have no
    `serial`. The two imported gather-facts plays do use `kolla_serial` (`gather-facts.yml:7,32`), as do all `nova.yml`
    plays.
  - `destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, `certificates.yml`, `bifrost.yml`
    (grep `serial:` count 0).
- **Bug: `--ask-vault-pass`** (`:385-388`):
  ```bash
  (--ask-vault-pass)
          VERBOSITY="$EXTRA_OPTS --ask-vault-pass"
  ```
  It should append to `EXTRA_OPTS`. Effects: any `-v` given **before** it is lost, and all `EXTRA_OPTS` collected so far
  (including the `EXTRA_OPTS` environment variable) are **repeated** after the playbook path (`:587`). Usually harmless,
  because
  the duplicated `-e`, `--tags` and `--limit` values are identical, but verbosity silently disappears.
- **Bug: `--include-dev`** is declared `include-dev:` (requires an argument) in `LONG_OPTS` (`:270`) but handled as a
  flag with
  `shift 1` (`:349-352`). getopt swallows the next word as its argument.
  `destroy --include-dev --yes-i-really-really-mean-it`
  only works by accident (the swallowed word is then re-parsed). `destroy --include-dev -i inv` mis-parses, and a
  trailing
  `--include-dev` errors out.
- **Bug/limitation:** `CMD="ansible-playbook $CONFIG_OPTS $EXTRA_OPTS $PLAYBOOK $VERBOSITY"` runs unquoted (`:142,587`).
  It is word-split (no spaces are possible inside `-e` JSON values) and pathname-expanded (for example
  `--limit compute[0-1]`
  could glob-match a file in the current directory).
- Environment check: refuses Ansible outside 2.13–2.14 (`:10-11,78-82`) and requires `kolla_ansible` importable by
  Ansible's Python (`:52-57`).
- Confirmation guard: `destroy`, `stop` and `prune-images` require `--yes-i-really-really-mean-it` (`:461,522,551`).
  `bootstrap-servers` (which can restart Docker everywhere) has **no** confirmation.

---

## 12. Ansible configuration and documented tuning

- FACT: **no `ansible.cfg` ships for users.** Repo-wide search found only:
  - `tests/templates/ansible.cfg.j2:1-10` (CI): `callback_plugins`, `host_key_checking = False`,
    `inject_facts_as_vars = False`
    (no exceptions any more); `[ssh_connection] pipelining = True`, `retries = 3`,
    `ssh_args = -C -o ControlMaster=auto -o ControlPersist=300`.
  - `contrib/dev/vagrant/bootstrap.sh:249-256` (dev): `forks=100`, `remote_user = root`, `scp_if_ssh=True`.
- Documentation recommendations:
  - `doc/source/user/quickstart.rst` no longer contains an `ansible.cfg` (grep for `ansible.cfg`, `pipelining`, `forks`
    is
    empty); it points to `kolla-ansible install-deps` for the collection (`quickstart.rst:128-135`).
  - `doc/source/user/ansible-tuning.rst`:
    - SSH pipelining `[ssh_connection] pipelining = True` (8-18).
    - `forks = 20` as an example; "experiment to find out the CPU, memory and IO limits" (20-34).
    - Fact caching: `gathering = smart`, `fact_caching = jsonfile`, `fact_caching_connection = /tmp/ansible-facts`, and
      an
      optional `fact_caching_timeout` (36-66); populating the cache with `kolla-ansible gather-facts` before a `--limit`
      run (68-85).
    - `inject_facts_as_vars = False` (87-104). FACT: the 2023.1 playbooks, the collection roles and the filters
      reference
      facts only through `ansible_facts` (grep for `ansible_[a-z_]+` other than `ansible_facts` returns only magic
      variables and kolla's own `ansible_version_min/max/host`), so this is safe for this tree.
    - Fact filtering `kolla_ansible_setup_filter: "ansible_[!qt]*"`, "reported to be as large as 18x" (106-129).
    - `kolla_ansible_setup_gather_subset: "all,!facter"` (131-140).
  - **Not documented anywhere in `doc/source`:** ControlPersist/`ssh_args`, mitogen, `strategy` (free/linear),
    `ANSIBLE_SERIAL`
    or `serial` for scale. The only `kolla_serial` mention is `bootstrap-servers.rst:83`. Large-scale guidance amounts
    to
    `--limit` per cell (`doc/source/reference/compute/nova-cells-guide.rst:376-394,426-449`) and the tuning page above.

---

## 13. Day-2 and scale knobs: `etc/kolla/globals.yml` and `ansible/group_vars/all.yml`

Defaults live in `all.yml` and, for bootstrap knobs, in the ansible-collection-kolla role defaults. `globals.yml` shows
commented examples. **Several Docker knobs are not listed in globals.yml at all** (`docker_log_max_*`,
`docker_disable_*`,
`docker_custom_config`, `docker_graceful_timeout`, `docker_restart_policy`, `docker_*_proxy`, `docker_registry_ca`;
grep), but they can still be overridden there.

| Knob | Default (file:line) | Day-2 / scale relevance |
|---|---|---|
| `kolla_ansible_setup_filter` / `kolla_ansible_setup_gather_subset` | `omit` (`all.yml:31,37`; `globals.yml:16,22`) | Fact size and time per host. Biggest win on computes with many tap/qvo interfaces. |
| `config_strategy` | `COPY_ALWAYS` (`all.yml:43`; `globals.yml:31`) | Containers re-copy config at every start, so a container that starts again after a Docker restart or reboot applies pending rendered config ([§2.4](#24-blast-radius-of-a-restart)) |
| `openstack_release` / `openstack_tag` / `openstack_tag_suffix` | `2023.1` / `<release>-<distro>-<distro version><suffix>` / `""` (`all.yml:578-581`; `globals.yml:37-43`, whose commented `openstack_tag` example differs from the `all.yml` default) | Image tag. No longer depends on `site.yml`-only facts ([§9](#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)). |
| `docker_registry`, `docker_registry_insecure`, `docker_namespace` | `quay.io` / `no` / `openstack.kolla` (`all.yml:98-102`; `globals.yml:86-93`) | **`insecure-registries` no longer follows the registry**: changing `docker_registry` rewrites daemon.json (and restarts Docker on every host at the next bootstrap-servers) only when `docker_registry_insecure` is true or a `docker_registry_ca` is set |
| `docker_log_max_file` / `docker_log_max_size` | `"5"` / `"50m"` (`all.yml:113-114`) | daemon.json, so a change means a restart |
| `docker_disable_default_iptables_rules` / `_network` / `ip_forward` | **`"yes"`** x3 (the last two follow the first, `all.yml:108-110`) | daemon.json, so a change means a restart. The first also drops `iptables` from the Docker package list (`docker/defaults/main.yml:27`). |
| `docker_storage_driver` / `docker_runtime_directory` / `docker_custom_config` | `""` / `""` / `{}` (`docker/defaults/main.yml:29-30`, `all.yml:103`) | In daemon.json (restart). `docker_custom_option` no longer exists. |
| `docker_http_proxy` / `docker_https_proxy` / `docker_no_proxy` | `""` (`docker/defaults/main.yml:32-34`) | systemd drop-in, **never applied by Kolla** ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |
| `docker_systemd_reload` | `false` (`docker/defaults/main.yml:63`) | `true` makes the handler reload instead of restart Docker |
| `docker_apt_package_pin` / `docker_yum_package_pin` | `""` (`docker/defaults/main.yml:13,21`) | Pins the Docker engine version; the package task stays `state: present` |
| `docker_restart_policy` / `docker_restart_policy_retry` | `unless-stopped` / `10` (`all.yml:117,120`) | Written into each container's systemd unit (`Restart=always` for `unless-stopped`); whether containers return after a daemon restart or reboot is NOT AVAILABLE ([§2.4](#24-blast-radius-of-a-restart)) |
| `docker_graceful_timeout` | `60` (`all.yml:140`) | **Now applied**: the unit's `ExecStop` and `kolla_docker` stops use it ([Repository architecture §6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). The stop timeout of a daemon restart is NOT AVAILABLE ([§2.4](#24-blast-radius-of-a-restart)). |
| `docker_client_timeout` | `120` (`all.yml:105`; `globals.yml:96`) | **Now applied**: passed in `docker_common_options` (`all.yml:153`) and used as the start timeout and unit `StartLimitIntervalSec` ([Repository architecture §6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker); `module_utils/kolla_systemd_worker.py:58`) |
| `docker_configure_for_zun` / `containerd_configure_for_zun` | `no` (`all.yml:123,129`) | Zun hosts: daemon.json includes **all etcd hosts**, and the containerd config is overwritten and restarted |
| `customize_etc_hosts`, `create_kolla_user`, `disable_firewall`, `change_selinux`/`selinux_state`, `enable_docker_repo`, `virtualenv` | true, **False**, True, True/permissive, true (not openEuler), none (`etc_hosts/defaults/main.yml:3`, `baremetal/defaults/main.yml:21,26-31`, `docker/defaults/main.yml:6`, `docker_sdk/defaults/main.yml:22`) | Host mutations made by bootstrap-servers ([§1](#1-ansiblekolla-hostyml-the-bootstrap-servers-command)) |
| `enable_nova_libvirt_container` | `true` for kvm/qemu (`all.yml:731`) | Removes host libvirt packages (and `iscsi-initiator-utils` on RedHat) and disables the libvirtd AppArmor profile during bootstrap. `enable_chrony` no longer exists (grep). |
| `neutron_plugin_agent` | `openvswitch` (`all.yml:277`; `globals.yml:157`) | Drives OVS and agent containers on every compute |
| `enable_neutron_dvr` / `neutron_compute_dvr_mode` / `computes_need_external_bridge` | `no` / `dvr` / derived (`all.yml:719,998-999`; `globals.yml:373`) | DVR puts L3 and metadata agents on **every compute**, and an external bridge per compute |
| `enable_neutron_agent_ha` | `no` (`all.yml:721`; `globals.yml:375`) | L3/DHCP agent HA on network nodes |
| `enable_neutron_provider_networks` | `no` (`all.yml:723`; `globals.yml:377`) | External bridge on computes |
| `nova_compute_virt_type` | `kvm` (`all.yml:1031`; `globals.yml:569`) | `nova_libvirt` is enabled for kvm and qemu |
| `enable_nova_ssh` | `yes` (`all.yml:733`) | nova_ssh container per compute (cold migration and resize) |
| `enable_cells` | `no` (`all.yml:646`; `globals.yml:305`) | Cell sharding for scale, together with `--limit cellNN` (nova-cells guide) |
| `openstack_service_workers` / `openstack_service_rpc_workers` | `min(vcpus,5)` / `min(vcpus,3)` (`all.yml:598-599`) | Caps API and RPC workers on large controllers (58 references in role templates and defaults, grep) |
| `database_max_pool_size` / `database_connection_recycle_time` | `1` / `10` (`all.yml:86-87`) | oslo.db pool per worker (used in the templates of 29 roles, grep) |
| `openstack_logging_debug` | `False` (`all.yml:582`; `globals.yml:279`) | Log volume. Combine with docker log rotation. |
| `enable_fluentd` / `enable_central_logging` | `yes` / `no` (`all.yml:665,647`) | Per-host fluentd container |
| `set_sysctl` / `kolla_sysctl_conf_path` | `yes` / `/etc/sysctl.conf` (`all.yml:602,605`) | Host sysctl writes from service `config-host.yml` (and the one bootstrap sysctl on RedHat) |
| `skip_stop_containers` | `[]` (`all.yml:784`) | Protects containers from `kolla-ansible stop` |
| `enable_destroy_images` | `no` (`all.yml:775`; `globals.yml:323`) | Whether destroy also removes images |
| `enable_mariabackup` | `no` (`all.yml:709`; `globals.yml:366`) | Must be `yes` or `mariadb_backup` silently does nothing |
| `kolla_enable_tls_backend` | `no` (`all.yml:847`) | Pulls `gather-facts.yml` into `certificates` |
| `keepalived_virtual_router_id` | `51` (`all.yml:189`; `globals.yml:180`) | Must be unique per L2 segment in multi-region setups |
| `<container>_dimensions` | `default_container_dimensions` (`all.yml:161-166`: nofile 1048576 on RedHat family, else `{}`), combined per role (e.g. `roles/nova-cell/defaults/main.yml:269`); `globals.yml:183-192` | CPU, memory and ulimit limits per container |

---

## 14. Register of open questions (NOT AVAILABLE, or answered from code)

| # | Question | Status | What the code shows |
|---|---|---|---|
| H1 | Does daemon-reload report changed in Ansible 2.8? | **Answered from code** (FACT) for the Ansible that 2023.1 runs: no. Ansible 2.8 is not supported by 2023.1 (`tools/kolla-ansible:10-11`) | ansible-core 2.14.18 `lib/ansible/modules/systemd.py:384-395` runs `daemon-reload` with `changed=False`; `changed` is set only at `:475,521,553`, so the reload handler never notifies the restart ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |
| H2 | Does an interrupted bootstrap leave docker masked on Debian/Ubuntu, so that docker does not start after reboot? | Symlink left in place unless the recovery block `docker/tasks/install.yml:44-72` or the "Restart docker" handler (both `masked: no`) already ran: FACT. Effect at reboot: NOT AVAILABLE | No `rescue`/`always` in the roles; a failed host runs no further task (ansible-core 2.14.18 `lib/ansible/executor/play_iterator.py:468-478`); systemd boot behaviour is not in the sources ([§2.3](#23-the-debianubuntu-mask-window)) |
| H3 | Does one fact-less baremetal host abort bootstrap-servers on all hosts (`/etc/hosts` task)? | **Answered from code** (FACT): yes, for a host outside `bifrost` with no gathered or cached facts | Empty `ansible_facts`, `kolla_address` raises on that host's line, and every host renders every line ([§3](#3-etchosts-generation)) |
| H4 | Does an unreachable non-limited host break `--limit` runs through delegated facts? | **Answered from code** (FACT): yes, unless its facts are cached | Its delegated item returns `unreachable`, which removes the limited host from the run ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| H5 | What is the wall time of `--limit` fact gathering? | NOT AVAILABLE | Each limited host runs about N/L delegated `setup` calls one after another, L hosts in parallel ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |
| H6 | What stop timeout does a Docker daemon restart apply to Kolla containers? | NOT AVAILABLE | `kolla_docker` sets no `StopTimeout`; `docker_graceful_timeout` reaches the systemd units and `kolla_docker` stops only ([§2.4](#24-blast-radius-of-a-restart)) |
| H7 | Does a simultaneous Docker restart on all controllers need `mariadb_recovery`? | NOT AVAILABLE | All notified hosts restart Docker in the same handler flush; the image has no Galera recovery logic ([§2.4](#24-blast-radius-of-a-restart)) |
| H8 | Do QEMU guests survive a nova_libvirt container restart? | NOT AVAILABLE | `pid_mode: host`, `cgroupns_mode: host` and a `/sys/fs/cgroup` bind mount ([§2.4](#24-blast-radius-of-a-restart)) |
| H9 | Does `kolla-libvirt-guests.service` (optional) shut guests down on a Docker restart? | NOT AVAILABLE | `kolla-libvirt-guests-docker.service` has `Requires=docker.service`; `ExecStop` runs `libvirt-guests.sh shutdown` ([§2.4](#24-blast-radius-of-a-restart)) |
| H10 | Does an option set both in the drop-in and in daemon.json make dockerd fail at the next restart? | NOT AVAILABLE | The role writes both files and restarts Docker only for daemon.json (or CA) changes ([§2.2](#22-why-docker_reloaded-never-triggers-a-restart)) |
| H11 | Does `apparmor_parser -R` fail on an already-unloaded profile (second run)? | **No longer arises** (FACT): the task links the profile into `/etc/apparmor.d/disable/` and is skipped once that link exists | `apparmor_libvirt/tasks/remove-profile.yml:7-22`. Whether `apparmor_parser -R` fails on an unloaded profile remains NOT AVAILABLE, but the role no longer runs it twice ([§1.3](#13-task-by-task-post-installyml)) |
| H12 | Do mariadb_backup and mariadb_recovery use the un-suffixed tag on CentOS Stream? | **No longer applies** (FACT) | The `-centos8s` suffix logic and `kolla_centos_release` are gone; the backup uses the running mariadb container's image (`roles/mariadb/tasks/backup.yml:18-21`, `group_vars/all.yml:580-581`) ([§9](#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)) |
| H13 | Is the backend TLS cert regenerated for new hosts? | **Answered from code** (FACT): no | `creates:` guards on the CSR and certificate steps ([§10](#10-certificatesyml-playbook-level)) |
| H14 | Does `kolla-ansible bootstrap-servers --check --diff --limit X` (or `EXTRA_OPTS="--check --diff"`) preview daemon.json changes safely? | NOT AVAILABLE | The CLI now has `--check`/`--diff` (`tools/kolla-ansible:316-324`). In check mode `copy` reports changed (with a diff) without writing (ansible-core 2.14.18 `lib/ansible/plugins/action/copy.py:285-293`), the systemd module runs no action (`lib/ansible/modules/systemd.py:391,481,554`), and `command` tasks without `creates`/`removes` are skipped (`lib/ansible/modules/command.py:323-331`); the collection modules used by the role (`ufw`, `selinux`, `sysctl`, `authorized_key`, `git_config`) are outside the sources |
| H15 | Do running containers see `/etc/hosts` updates? | NOT AVAILABLE | The task edits the host's `/etc/hosts` only ([§3](#3-etchosts-generation)) |
| H16 | Does the `ansible_[!qt]*` filter break hosts whose api/tunnel interface starts with q or t? | **Answered from code** (FACT): yes | The filter is matched against fact names, and `kolla_address` raises for a missing interface ([§4](#4-ansiblegather-factsyml-confirmed-and-its-cost-model)) |

## 15. Operational recommendations from this code

1. Before any `bootstrap-servers` re-run on production, render the target daemon.json and compare it with the hosts
   (`kolla-ansible bootstrap-servers --check --diff --limit <one host>`; whether check mode makes this safe is NOT
   AVAILABLE, H14). Expect a difference on the first 2023.1 run of a host bootstrapped by an older release. If it
   differs, run with `-e kolla_serial=1`, or with `--limit` per controller and in compute batches, keeping Galera
   and RabbitMQ quorum.
2. Do not rely on the systemd drop-in (`docker_*_proxy`, Zun options) being applied by Kolla. Put options in
   `docker_custom_config` (daemon.json) so changes are applied, and are applied visibly; schedule a controlled Docker
   restart after changing proxy settings.
3. After any failed or interrupted run on Debian/Ubuntu, check for a masked `docker.service`, and compare daemon.json
   with
   the running daemon: a host that failed before the handler flush has a new daemon.json that no later run will apply.
4. Set `disable_firewall: false`, `change_selinux: false` and the package-removal lists (`ubuntu_pkg_removals`,
   `redhat_pkg_removals`) explicitly if the hosts are managed by other tooling. Check `open-iscsi` and
   `iscsi-initiator-utils` before the first run on hosts that use host iSCSI. Set `create_kolla_user: true` explicitly
   if you rely on the `kolla` user.
5. At scale, enable jsonfile fact caching with `gathering = smart`, `inject_facts_as_vars = False` and a setup filter,
   and
   fill the cache with `kolla-ansible gather-facts` before `--limit` runs. Without them, `--limit` runs gather facts for
   the whole inventory, one host at a time per limited host.
6. Use `ANSIBLE_SERIAL` (not `-e kolla_serial`) for `reconfigure` and `upgrade`. Always pass `-i`.
7. Never run `destroy` without `--limit`. Exclude the deploy host (`--limit '!localhost'`) unless you want its
   `/etc/kolla` wiped.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)

---
title: Stop and destroy
description: The stop and destroy command lines in 2025.1, both rated Critical, with the new Python CLI, max_fail_percentage and the inventory paths destroy keeps.
tags: [stop, destroy, migrate-container-engine, risk, podman, max-fail-percentage]
impact: [critical]
---

# Stop and destroy

The command lines of `kolla-ansible stop` and `kolla-ansible destroy` in 2025.1, which the study files under
"dangerous", and the changes of 2025.1 that touch them: the Python CLI that now parses their options, the new
`stop --ignore-missing`, and the inventory paths that `destroy` keeps, now read from Ansible itself. What each command
stops or removes in detail is described in the sections listed under [Related](#related).

> [!CAUTION]
> The risk register rates both commands Critical: `kolla-ansible stop` ([R15](../risk/risk-register.md#r15)) and
> `kolla-ansible destroy` ([R16](../risk/risk-register.md#r16)). `destroy` targets `hosts: all`, which includes the
> deploy host (`destroy.yml:2-3`, `inventory/multinode:32-33`); only what you pass with `--limit` narrows it. Never run
> it on production. **New in 2025.1:** `kolla-ansible migrate-container-engine` also stops every container on every
> baremetal host, and asks for no confirmation ([Fact sheet E
> §6.1](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#61-migrate-container-engine-new-in-20251)).

```bash
kolla-ansible stop -i multinode --yes-i-really-really-mean-it -t heat --limit control03
kolla-ansible destroy -i multinode --yes-i-really-really-mean-it   # never on production
```

- **Confirmation.** Both refuse to run without `--yes-i-really-really-mean-it` [CODE]: in the 2025.1 Python CLI the
  option is declared `required=True` for both sub-commands (`kolla_ansible/cli/commands.py:285-296, :318-329`).
  **Changed in 2025.1:** the sub-command comes first and its options follow it, as in the example above
  ([Fact sheet E §11](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#11-kolla-ansible-cli)). `stop` runs
  `site.yml` with `kolla_action=stop`, so `-t` and `--limit` narrow it; `destroy` runs `destroy.yml`
  (`kolla_ansible/cli/commands.py:304-315, :343-359`).
- **What `stop` does.** Each role's `stop.yml` imports `service-stop`, which runs `kolla_container` `stop_container`
  for each enabled container mapped to the host [CODE] (e.g. `roles/heat/tasks/stop.yml:2-6`,
  `roles/service-stop/tasks/main.yml:2-13`; containers that a role runs several times, such as the OVN relays, are
  stopped one by one by `roles/service-stop/tasks/iterated.yml:2-14`). The stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`, 60 s by default: with Docker when the
  unit exists, `docker stop` otherwise; with Podman always through the unit, except for one-shot containers
  (`module_utils/kolla_docker_worker.py:426-442`, `module_utils/kolla_podman_worker.py:677-695`,
  `module_utils/kolla_systemd_worker.py:33`, `group_vars/all.yml:148, :160`). The stop path does not disable the unit,
  which `create_unit_file` enabled (`module_utils/kolla_systemd_worker.py:38-39, :173-186`). [NOT AVAILABLE] Whether
  systemd starts a stopped container again at the next boot of the host.
- **New in 2025.1: `stop --ignore-missing`.** By default `stop_container` fails the task when a container does not
  exist; with `--ignore-missing` the CLI passes `kolla_action_stop_ignore_missing=yes` and the task skips missing
  containers instead (`kolla_ansible/cli/commands.py:297-311`, `roles/service-stop/tasks/main.yml:10`,
  `module_utils/kolla_docker_worker.py:431-436`) [CODE].
- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`) [CODE]
  (`roles/service-stop/tasks/main.yml:11-12`, default `[]` in `group_vars/all.yml:993`).
- **Still holds in 2025.1: `max_fail_percentage` on the plays of both commands.** Every play of `site.yml`, and the
  single play of `destroy.yml`, sets `max_fail_percentage: {{ <svc>_max_fail_percentage |
  default(kolla_max_fail_percentage) | default(100) }}` (e.g. `site.yml:96-99`, `destroy.yml:4-7`) [CODE]. With the
  default 100, a host that fails drops out and the others carry on: ansible-core 2.18.20 breaks a play only when the
  failed hosts of the current batch exceed that share of the batch, and otherwise stops the playbook only when every
  host of a batch failed (`lib/ansible/plugins/strategy/linear.py:335-349`,
  `lib/ansible/executor/playbook_executor.py:196-209, :214-215`). `stop` passes no `kolla_serial` and `destroy.yml` sets
  no `serial`, so each play runs its hosts in one batch unless you add `-e kolla_serial=N` to `stop`
  (`kolla_ansible/cli/commands.py:307-315`, `destroy.yml:2-9`). A lower value (`kolla_max_fail_percentage`, or
  `destroy_max_fail_percentage` for `destroy`) ends the run once the share is exceeded; the check comes after the
  task has run on every host of the batch (`lib/ansible/plugins/strategy/linear.py:195, :215-216, :335-349`), so it
  stops the following tasks and plays, not the task that failed.
- **What `destroy` runs.** The role runs, in order, a check that `sudo <engine> ps` works, `tools/cleanup-containers`,
  `tools/cleanup-images` (only with images included) and `tools/cleanup-host` (`roles/destroy/tasks/main.yml:2-7`,
  `roles/destroy/tasks/validate_docker_execute.yml:2-5`, `roles/destroy/tasks/cleanup_containers.yml:2-3`,
  `roles/destroy/tasks/cleanup_images.yml:2-5`, `roles/destroy/tasks/cleanup_host.yml:2-16`) [CODE]. Each script is
  given `kolla_container_engine`, and `cleanup-containers` accepts only `docker` or `podman`
  (`tools/cleanup-containers:4-10`). It exits with an error, before it removes anything, when `nova_libvirt` runs and
  QEMU processes are found (`:16-22`).
- **Still holds in 2025.1: `cleanup-containers` disables the units.** For each Kolla container it disables, stops and,
  if failed, resets `kolla-<name>-container.service`, then removes the containers, their volumes, the `/var/log/kolla`
  link and every `kolla-*-container.service` file (`tools/cleanup-containers:43-67`) [CODE].
- **Changed in 2025.1: the inventories come from Ansible.** The role hands `ansible_inventory_sources`, joined with
  spaces, to `cleanup-host` as `kolla_ansible_inventories` (`roles/destroy/tasks/cleanup_host.yml:16`); the CLI no
  longer passes `inventories_comma_separated`. `cleanup-host` removes every entry of `/etc/kolla` except
  `passwords.yml`, `globals.yml`, `globals.d`, `kolla-build.conf`, `config`, `certificates` and the entries equal to
  one of those inventory paths (`tools/cleanup-host:65, :72-97`) [CODE]. ansible-core makes every `-i` path absolute and
  normalised, relative to the current directory and without resolving symlinks (ansible-core 2.18.20
  `lib/ansible/cli/__init__.py:430`, `lib/ansible/utils/path.py:30-62`, `lib/ansible/utils/vars.py:230-249`). So a
  relative `-i multinode` given from `/etc/kolla` now keeps `/etc/kolla/multinode`; an inventory inside a
  subdirectory of `/etc/kolla` (for example `/etc/kolla/inventory/hosts`) matches no entry, and that entry is removed.
  Without `-i` the CLI passes `<configdir>/ansible/inventory/all-in-one` (`kolla_ansible/ansible.py:144-152`), which
  matches no entry of `/etc/kolla` either.
- `destroy` also removes the images with `--include-images` (or `enable_destroy_images: yes`, default `no`) [CODE]
  (`kolla_ansible/cli/commands.py:336-340, :353-355`; `roles/destroy/defaults/main.yml:2`, `group_vars/all.yml:984`,
  `roles/destroy/tasks/cleanup_images.yml:3-5`; `tools/cleanup-images --all` removes every image with the
  `kolla_version` label, `tools/cleanup-images:60-63, :94`). With `--include-dev` (`destroy_include_dev`), it removes the
  dev-mode repositories under `kolla_dev_repos_directory` (`roles/destroy/defaults/main.yml:3`,
  `group_vars/all.yml:60`; `tools/cleanup-host:99-102`).
- **Changed in 2025.1: `--include-dev` is a plain flag** (`action="store_true"`, `kolla_ansible/cli/commands.py:331-335,
  :350-352`) [CODE]. The 2024.1 getopt declaration that made it look like an option taking a value is gone with the
  Bash wrapper.

## Related

- [R15](../risk/risk-register.md#r15) — `kolla-ansible stop`: it stops all Kolla containers on the targeted hosts, and
  MariaDB then needs `mariadb-recovery`
- [R16](../risk/risk-register.md#r16) — `kolla-ansible destroy`: what it removes on the targeted hosts, the deploy
  host included
- [Fact sheet E
  §6](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)
  — `destroy` in detail: `destroy.yml`, the `destroy` role and the `tools/cleanup-*` scripts, and §6.1,
  `migrate-container-engine`
- [Fact sheet E §11](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#11-kolla-ansible-cli) — the 2025.1 CLI
  and its confirmation guard
- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the row
  `stop` of the action matrix
- [Write config first, apply in controlled batches
  §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage) — how `max_fail_percentage` stops
  a run
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  after `stop`, the next deploy or reconfigure fails until `mariadb-recovery` is run
- [Database operations](database-operations.md) — the `mariadb-recovery` command
- [Update container images §1.2](update-container-images.md#12-prune-old-images) — `prune-images`, which removes
  images without stopping containers
- [2024.1 stop and destroy](../../2024.1/operations/stop-and-destroy/) — the same page for 2024.1

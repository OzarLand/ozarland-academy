---
title: Repository architecture
description: "How Kolla-Ansible 2023.1 is built: entry points, from CLI command to ansible-playbook, site.yml, role anatomy, custom modules, the collection."
tags: [deploy, reconfigure, genconfig, handlers, kolla-set-configs, serial, images, inventory, docker]
remember:
  - "<code>reconfigure</code> is <code>deploy</code>: it re-runs Keystone registration, DB creation and the bootstrap (DB sync) container of most services. <span class=\"ev ev-code\">CODE</span>"
  - "A config change is applied by a full stop/start, never a reload: the restart handler recreates or restarts the container. <span class=\"ev ev-code\">CODE</span>"
  - "The stop timeout is the 60 s of <code>docker_graceful_timeout</code>, written into each container's systemd unit (<code>docker stop -t 60</code>). <span class=\"ev ev-code\">CODE</span>"
  - "<code>deploy</code> and <code>reconfigure</code> pull an image only if it is absent locally; a rebuilt image pushed under the same tag takes an explicit <code>pull</code>. <span class=\"ev ev-code\">CODE</span>"
  - "Batching is off by default: <code>ANSIBLE_SERIAL</code> defaults to 0, which means all hosts of a play in one batch. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "How is a configuration change applied to a running container?"
    options: ["The service reloads its configuration inside the container", "By a full stop and start: the container is recreated or restarted", "At the next reboot of the host"]
    answer: 1
    explain: "A config change is applied by a full stop/start, never a reload: the restart handler recreates the container when the image or parameters differ and otherwise restarts it <span class=\"ev ev-code\">CODE</span>."
    see: "43-the-config--check--handler-pattern"
  - q: "A rebuilt image is pushed under the same tag. Does <code>reconfigure</code> use it?"
    options: ["Yes, <code>reconfigure</code> always pulls the images", "No: <code>deploy</code> and <code>reconfigure</code> pull an image only if it is absent locally"]
    answer: 1
    explain: "Using the rebuilt image takes an explicit <code>pull</code> <span class=\"ev ev-code\">CODE</span>."
    see: "6-custom-modules--container-lifecycle-via-kolla_docker"
  - q: "How long does Kolla-Ansible wait when it stops a container?"
    options: ["10 s", "60 s, the value of <code>docker_graceful_timeout</code>", "It does not wait"]
    answer: 1
    explain: "The 60 s of <code>docker_graceful_timeout</code> reaches the module and is written into each container's systemd unit (<code>docker stop -t 60</code>) <span class=\"ev ev-code\">CODE</span>. The Ussuri bug that forced 10 s is fixed."
    see: "6-custom-modules--container-lifecycle-via-kolla_docker"
---

# Repository architecture

This page explains *how the machine is built*: which entry points exist, how a CLI command becomes an
`ansible-playbook` run, how `site.yml` is laid out, what every service role has in common, and which custom modules
actually touch the hosts. The other pages build on the vocabulary defined here.

> [!NOTE]
> **Key answers**
>
> - **`reconfigure` is `deploy`.** Of the 59 roles that have a `reconfigure.yml`, 56 only do `import_tasks: deploy.yml`,
>   so `reconfigure` re-runs Keystone registration, DB creation and the bootstrap (DB sync) container of most services
>   [CODE] ([§4.2](#42-reconfigure-is-deploy)).
> - **A config change is applied by a full stop/start, never a reload.** A changed file, a changed container definition,
>   a changed systemd unit or drift reported by `kolla_set_configs --check` notifies the restart handler, which
>   recreates the container when the image or parameters differ and otherwise restarts its systemd unit [CODE]
>   ([§4.3](#43-the-config--check--handler-pattern)).
> - **The stop timeout is the 60 s of `docker_graceful_timeout`.** The Ussuri bug that forced 10 s is fixed: the value
>   from `docker_common_options` now reaches the module and is written into each container's systemd unit
>   (`docker stop -t 60`) [CODE] ([§6](#6-custom-modules--container-lifecycle-via-kolla_docker)).
> - **`deploy` and `reconfigure` pull an image only if it is absent locally** (`start_container`). A rebuilt image
>   pushed under the same tag is not fetched by `deploy` or `reconfigure`; it takes an explicit `pull` [CODE]
>   ([§6](#6-custom-modules--container-lifecycle-via-kolla_docker)).
> - **Batching is off by default.** `ANSIBLE_SERIAL` defaults to 0, which means all hosts of a play in one batch, and
>   the wrapper passes `kolla_serial` only for `reconfigure` and `upgrade` [CODE]
>   ([§2](#2-from-cli-to-ansible-playbook)).
> - **`common` is a play of its own, tagged `common`.** No role has a meta dependency on it any more and the
>   `common_run` guard is gone: `-t common reconfigure` now renders and restarts the common containers, and `-t nova`
>   no longer runs `common` [CODE] ([§5.1](#51-the-common-role-and-the-common_run-guard)).
> - **Host bootstrap moved out of the repository.** `bootstrap-servers` runs `openstack.kolla.baremetal` from
>   ansible-collection-kolla, which `kolla-ansible install-deps` installs from `requirements.yml` [CODE]
>   ([§1](#1-top-level-layout)).

> Scope: the `2023.1-eol` tag of `openstack/kolla-ansible` (commit `4891a21`), with ansible-collection-kolla at the
> `unmaintained/2023.1` branch that `requirements.yml` pins (studied at its `2023.1-eol` tag). Every path below is
> relative to the root of the kolla-ansible checkout; paths prefixed `ansible-collection-kolla`, `kolla` or
> `ansible-core 2.14.18` point into the collection, the kolla image repository or the Ansible source. The evidence
> labels **[CODE]** and **[NOT AVAILABLE]** are defined once, in [Evidence
> labels](../start/conventions.md#evidence-labels).

---

## 1. Top-level layout

| Path | What it is | Why it matters for Day 2 |
|---|---|---|
| `tools/kolla-ansible` | Bash wrapper. Maps sub-commands to a playbook plus `-e kolla_action=<action>`; checks that ansible-core is between 2.13 and 2.14 (`tools/kolla-ansible:10-11`) | Decides which playbook runs and whether `kolla_serial` is passed ([§2](#2-from-cli-to-ansible-playbook)) |
| `requirements.yml` | Ansible Galaxy requirements: one collection, `https://opendev.org/openstack/ansible-collection-kolla`, `type: git`, `version: unmaintained/2023.1` (`requirements.yml:2-5`) | Installed by `kolla-ansible install-deps` (`ansible-galaxy collection install -r requirements.yml --force`, `tools/kolla-ansible:131-138, :429-432`). Without it `bootstrap-servers` cannot find its role. A branch, not a tag: what is installed is whatever the branch holds at install time |
| ansible-collection-kolla (`openstack.kolla`, `galaxy.yml:2-3`) | Separate repository, roles only (no modules or plugins): `baremetal`, `docker`, `docker_sdk`, `etc_hosts`, `kolla_user`, `packages`, `apparmor_libvirt` | Holds the host-bootstrap code that was `roles/baremetal` in Ussuri. kolla-ansible references it in one place: `kolla-host.yml:9` (`role: openstack.kolla.baremetal`); `baremetal` imports `etc_hosts`, `packages`, `docker`, `kolla_user`, `docker_sdk` and `apparmor_libvirt` (ansible-collection-kolla `roles/baremetal/tasks/main.yml:2-3`, `install.yml:34-38`, `post-install.yml:2-19`) |
| `ansible/site.yml` | The main playbook (79 plays once `gather-facts.yml`, `mariadb.yml`, `rabbitmq.yml` and `nova.yml` are expanded) | Every `deploy`, `reconfigure`, `upgrade`, `pull`, `stop`, `prechecks`, `genconfig`, `validate-config`, `deploy-containers` run goes through it |
| `ansible/gather-facts.yml` | Imported first by `site.yml` (and by `kolla-host.yml`) | Fact gathering, including the special `--limit` path (see [Compute scaling](compute-scaling-and-performance.md)) |
| `ansible/mariadb.yml`, `ansible/rabbitmq.yml` | Imported by `site.yml:385` and `:438` | MariaDB in 5 plays, RabbitMQ and outward RabbitMQ in 3 plays each; the restart plays use `serial: "33%"` (`mariadb.yml:20, :34`; `rabbitmq.yml:32, :88`) |
| `ansible/nova.yml` | Imported by `site.yml:544` | Nova is split into 10 plays (see [Nova deep dive](../components/nova-deep-dive.md)) |
| `ansible/kolla-host.yml` | `bootstrap-servers`: `gather-facts.yml`, then one play on `baremetal` with `serial: kolla_serial` applying `openstack.kolla.baremetal` (`kolla-host.yml:1-10`) | Installs Docker and changes the host OS. Can restart the Docker daemon (ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`) |
| `ansible/destroy.yml`, `prune-images.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, `certificates.yml`, `octavia-certificates.yml`, `bifrost.yml`, `monasca_cleanup.yml`, `nova-libvirt-cleanup.yml`, `rabbitmq-reset-state.yml`, `rabbitmq-upgrade.yml` | Single-purpose playbooks | See [Operations](../operations/index.md) |
| `ansible/roles/` | 79 roles, none with a `meta/` directory. 59 are applied by the plays of `site.yml` (56 service roles plus `prechecks`, `common` and `loadbalancer`); 5 by their own playbooks (`bifrost`, `certificates`, `octavia-certificates`, `destroy`, `prune-images`); `kafka`, `storm`, `zookeeper` and `monasca` only by `monasca_cleanup.yml`; 11 are helper roles imported by the others | [§4](#4-anatomy-of-a-service-role) and [§5](#5-shared-helper-roles) |
| `ansible/group_vars/all.yml` | 1,288 lines of defaults (every `enable_*`, ports, transport URLs, Docker options, `kolla_container_engine: "docker"` at `:92`) | Lowest-priority defaults. `globals.yml` overrides them |
| `ansible/inventory/{all-in-one,multinode}` | Example inventories that define 222 groups each | Group membership drives where every container runs |
| `ansible/library/` | Custom modules: `kolla_docker`, `kolla_toolbox`, `kolla_container_facts`, `kolla_container_volume_facts` | Main container interface: the service roles' container lifecycle goes through `kolla_docker`. Many role tasks also run `{{ kolla_container_engine }} exec`/`inspect` directly ([§6](#6-custom-modules--container-lifecycle-via-kolla_docker)) |
| `ansible/module_utils/` | `kolla_container_worker.py` (shared comparison logic), `kolla_docker_worker.py` (Docker SDK calls), `kolla_systemd_worker.py` (one systemd unit per container) | Where `kolla_docker` actually decides and acts ([§6](#6-custom-modules--container-lifecycle-via-kolla_docker)) |
| `ansible/action_plugins/` | `merge_configs` (INI merge) and `merge_yaml` | How `/etc/kolla/config` overrides are merged ([§7](#7-configuration-generation-and-overrides)) |
| `ansible/filter_plugins/`, `kolla_ansible/*.py` | Jinja filters: `service_enabled_and_mapped_to_host`, `select_services_enabled_and_mapped_to_host`, `kolla_address`, `extract_cell`, `customise_fluentd`, `database_shards_info`, … | Decide placement of a service on a host ([§4.4](#44-containers-and-placement)) |
| `etc/kolla/globals.yml`, `etc/kolla/passwords.yml` | Templates copied to `/etc/kolla/` by the operator | `globals.yml` (and every `*.yml` in `/etc/kolla/globals.d/`) is passed as **extra-vars** ([§2.1](#21-variable-precedence-that-matters)) |
| `tools/cleanup-*`, `tools/kolla-libvirt-guests-{docker,podman}.service`, `tools/virt-guest-shutdown.target` | Host utilities | `cleanup-host` deletes network namespaces and links (`tools/cleanup-host:5-22`; see [Risk register](../risk/risk-register.md)) |
| `doc/source/` | Documentation (`user/ansible-tuning.rst`, `reference/deployment-and-bootstrapping/bootstrap-servers.rst`, …) | Used only to cross-check, never as the source of truth |

No `ansible.cfg` is shipped for operators [CODE: no `ansible.cfg` in the kolla-ansible tree; [fact sheet E
§12](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#12-ansible-configuration-and-documented-tuning)]. Forks,
pipelining, fact caching and SSH settings come from whatever `ansible.cfg` or environment the operator provides.

---

## 2. From CLI to `ansible-playbook`

`tools/kolla-ansible` builds a single command line (`tools/kolla-ansible:583-591`):

```bash
GLOBALS_DIR="${CONFIG_DIR}/globals.d"
EXTRA_GLOBALS=$([ -d "${GLOBALS_DIR}" ] && find ${GLOBALS_DIR} -maxdepth 1 -type f -name '*.yml' -printf ' -e @%p' || true 2>/dev/null)
CONFIG_OPTS="-e @${CONFIG_DIR}/globals.yml ${EXTRA_GLOBALS} -e @${PASSWORDS_FILE} -e CONFIG_DIR=${CONFIG_DIR}"
CMD="ansible-playbook $CONFIG_OPTS $EXTRA_OPTS $PLAYBOOK $VERBOSITY"
for INVENTORY in ${INVENTORIES[@]}; do
    CMD="${CMD} --inventory $INVENTORY"
done
```

| Command | Playbook | Extra vars added | `kolla_serial` passed? | Evidence |
|---|---|---|---|---|
| `prechecks` | `site.yml` | `kolla_action=precheck` | no | `tools/kolla-ansible:433-436` |
| `check` | – | the sub-command no longer exists; it falls to `usage` and exit 3 | – | `:578-580` |
| `bootstrap-servers` | `kolla-host.yml` | `kolla_action=bootstrap-servers` | no (the playbook has its own `serial: kolla_serial`) | `:471-475` |
| `deploy` | `site.yml` | `kolla_action=deploy` | **no** | `:476-479` |
| `deploy-containers` | `site.yml` | `kolla_action=deploy-containers` | no | `:485-488` |
| `pull` | `site.yml` | `kolla_action=pull` | no | `:502-505` |
| `upgrade` | `site.yml` | `kolla_action=upgrade -e kolla_serial=${ANSIBLE_SERIAL}` | **yes** | `:506-509` |
| `reconfigure` | `site.yml` | `kolla_action=reconfigure -e kolla_serial=${ANSIBLE_SERIAL}` | **yes** | `:515-518` |
| `genconfig` | `site.yml` | `kolla_action=config` | no | `:540-543` |
| `validate-config` | `site.yml` | `kolla_action=config_validate` | no | `:544-547` |
| `stop` | `site.yml` | `kolla_action=stop` (needs `--yes-i-really-really-mean-it`) | no | `:519-531` |
| `destroy` | `destroy.yml` | (needs `--yes-i-really-really-mean-it`) | no | `:452-470` |
| `mariadb_recovery` | `mariadb_recovery.yml` | `kolla_action=deploy` | no | `:437-441` |
| `mariadb_backup` | `mariadb_backup.yml` | `kolla_action=backup -e mariadb_backup_type=<full\|incremental>` | no | `:442-446` |
| `post-deploy` | `post-deploy.yml` | – | no | `:498-501` |
| `prune-images` | `prune-images.yml` | (needs `--yes-i-really-really-mean-it`) | no | `:548-559` |
| `install-deps` | – | runs `ansible-galaxy collection install -r requirements.yml --force` and exits | – | `:131-138, :429-432` |

The 2023.1 wrapper also has `deploy-bifrost`, `deploy-servers`, `upgrade-bifrost`, `gather-facts`, `certificates`,
`octavia-certificates`, `monasca_cleanup`, `nova-libvirt-cleanup`, `rabbitmq-reset-state` and `rabbitmq-upgrade`
(`:447-451, :480-497, :510-514, :532-539, :560-573`), none of which passes `kolla_serial`.

Consequences [CODE]:

- **`ANSIBLE_SERIAL` defaults to 0** (`tools/kolla-ansible:288-290`), which means *all hosts of a play in one batch*.
  The comment there reads "Serial is not recommended and disabled by default".
- **`kolla_serial` is overridden for `reconfigure` and `upgrade`.** The wrapper appends
  `-e kolla_serial=${ANSIBLE_SERIAL}` *after* the user's `-e` options. For those two commands a user-supplied
  `-e kolla_serial=N` is therefore silently replaced by `ANSIBLE_SERIAL`. Use the environment variable instead ([fact
  sheet E §11](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#11-toolskolla-ansible-cli)).
- **Other commands default to 0.** For `deploy` and the rest, `kolla_serial` is not passed, and the plays fall back
  to `kolla_serial|default("0")`.
- **`--tags`, `--skip-tags`, `--limit`, `--forks`, `--check` and `--diff` pass straight through** (`:306-324`,
  `:370-378`). `EXTRA_OPTS` from the environment is passed through as well (`:282`), which is the only way to reach
  `--list-tasks`, `--list-tags` or `--list-hosts` through the wrapper.
- **`-i` can be given several times, and without it no inventory is passed.** Each `-i` adds a `--inventory`
  (`:296-299, :588-590`). The `INVENTORY` default to `ansible/inventory/all-in-one` (`:279`) is never used: the loop
  variable overwrites it, so a command without `-i` runs on whatever inventory the Ansible configuration names.
- **`/etc/kolla/globals.d/*.yml` are extra-vars too**, loaded after `globals.yml` and before `passwords.yml`
  (`:583-586`).
- **Bug: `--ask-vault-pass`.** The branch sets `VERBOSITY="$EXTRA_OPTS --ask-vault-pass"` (`:385-388`), which
  duplicates all options seen so far and drops earlier `-v` flags.

### 2.1 Variable precedence that matters

`globals.yml` and `passwords.yml` are passed with `-e @file`. That is **extra-vars, the highest precedence in Ansible**:
Ansible merges role defaults first, group vars and host vars later, and extra-vars last (ansible-core 2.14.18
`lib/ansible/vars/manager.py:198-221, :290-302, :420`). Consequences [CODE]:

- A value in `globals.yml` cannot be overridden per host or per group in the inventory. Per-host variation
  must come from variables that are *not* set in `globals.yml`. Inventory `host_vars` override role defaults and
  `group_vars/all.yml`, but not extra-vars.
- Anything placed in `globals.yml` (or `globals.d/`) applies to **every play and every host**. This is why "global"
  switches such as `enable_barbican`, `openstack_tag` or `nova_compute_virt_type` have fleet-wide effects (see
  [Operations](../operations/index.md)).
- The same holds for the collection: `openstack.kolla.baremetal` and the roles it imports read the variables of the
  run, so a Docker or host setting placed in `globals.yml` overrides the collection's role defaults.

---

## 3. Anatomy of `site.yml`

```mermaid
flowchart TB
  subgraph pre["Always-run plays (tag: always)"]
    GF1["gather-facts.yml play 1<br/>setup on all hosts<br/>(skipped if facts cached)"] --> GF2["gather-facts.yml play 2<br/>delegated setup when --limit is used"]
    GF2 --> GB["Group hosts based on configuration<br/>group_by: kolla_action_*,<br/>enable_&lt;svc&gt;_True/False"]
  end
  GB --> PRE["Apply role prechecks<br/>(hosts: kolla_action_precheck)"]
  PRE --> COM["common (cron, fluentd, kolla-logs, kolla-toolbox hosts; tag: common)"]
  COM --> INFRA["loadbalancer (+44 loadbalancer includes) → collectd → influxdb → telegraf → redis<br/>→ mariadb.yml (5 plays) → memcached → prometheus → iscsi → multipathd<br/>→ rabbitmq.yml (6 plays) → etcd"]
  INFRA --> CP1["keystone → opensearch → swift → ceph-rgw → glance → ironic → cinder → placement"]
  CP1 --> NOVA["nova.yml (10 plays)"]
  NOVA --> NET["openvswitch | ovs-dpdk → ovn-controller → ovn-db → neutron → kuryr → hacluster"]
  NET --> CP2["heat → horizon → murano → solum → magnum → mistral → sahara → manila → gnocchi → ceilometer<br/>→ aodh → barbican → cyborg → designate → trove → watcher → grafana → cloudkitty → freezer<br/>→ senlin → tacker → octavia → zun → vitrage → blazar → masakari → venus → skyline"]
```

Facts about the structure [CODE, `ansible/site.yml`]:

1. **One play per service, in a fixed order.** There is no dependency resolver. The deployment order *is* the order of
   plays in `site.yml` (see [Execution flow](deployment-execution-flow.md)). The only exception is the loadbalancer
   play, the "haproxy play" of Ussuri (`site.yml:99-341`): it runs *before* the services it fronts, and configures all
   of their frontends in one place through 44 `include_role … tasks_from: loadbalancer`, run only for `deploy`,
   `reconfigure`, `upgrade` and `config` (`site.yml:339-341`).
2. **The "group by configuration" optimisation.** The play at `site.yml:7-77` puts every host into groups such as
   `enable_nova_True`. Every service play then intersects its host list with `&enable_<svc>_True`, for example
   `hosts: [compute, …, '&enable_nova_True']`. If a service is disabled, the play matches no host and Ansible skips
   it entirely, which avoids evaluating hundreds of `when:` clauses per host. The NOTE at `site.yml:4-6` says this
   exists because "in large environments, even tasks that are skipped can take a significant amount of time".
3. **Serial and tags differ between plays.** Almost every play has `serial: '{{ kolla_serial|default("0") }}'`.
   - **Exceptions:** the setup plays `Group hosts based on configuration` and `Apply role prechecks`
     (`site.yml:7-84`) have no `serial` key. MariaDB and RabbitMQ are no longer single plays: their *apply* and
     *post-configuration* plays have no `serial` key (all members in one batch), while their *restart* plays use a fixed
     `serial: "33%"` that `ANSIBLE_SERIAL` does not change (`mariadb.yml:14-40`, `rabbitmq.yml:26-41, :82-98`). The
     handlers only sort hosts into the `mariadb_restart`/`rabbitmq_restart` groups; the restart itself happens in
     those plays
     ([fact sheet B §1–2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb);
     [Tags](../risk/tags.md)). The Ussuri `Check CentOS variant` play no longer exists.
   - **Bug: `cyborg` (`site.yml:784`)** uses `serial|default("0")`, not `kolla_serial`, so `ANSIBLE_SERIAL` has no
     effect on cyborg.
   - **Tag placement varies:**
     - Most plays tag the *role*, e.g. `roles: - { role: kuryr, tags: kuryr }`.
     - The `common` and loadbalancer plays, the `mariadb.yml` and `rabbitmq.yml` plays and all `nova.yml` plays put
       tags at *play* level (`site.yml:94-95, :105-108`).
     - `memcached` has two tags, `[memcache, memcached]` (`site.yml:394-395`); `ovn-controller` and `ovn-db` share
       `ovn` (`site.yml:575-576, :587-588`).
     - The `prechecks` play has no tag at all.
4. **`common` is a play, not a dependency.** No role has a `meta/` directory, so nothing pulls `common` in. It runs in
   its own play, `Apply role common`, on the hosts of `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`
   (`site.yml:86-97`), which in the example inventories are children of `common` = control, network, compute,
   storage, monitoring (`ansible/inventory/multinode:48-53, :239-249`)
   ([§5.1](#51-the-common-role-and-the-common_run-guard)).

The complete table of 79 plays (hosts, tags, serial) is generated from the source in [Generated inventory
§1](../reference/generated-inventory.md#1-plays-executed-by-siteyml-in-order).

---

## 4. Anatomy of a service role

Every service role follows the same skeleton. `glance` is a typical example (in 2023.1 `nova` keeps its bootstrap in
separate `nova.yml` plays, so its `deploy.yml` has no bootstrap step):

```text
roles/<svc>/
  defaults/main.yml      <svc>_services dict (containers), images, volumes, healthchecks, ks users/endpoints, ports
  vars/main.yml          project_name (and, for nova-cell, kolla_role_name)
  handlers/main.yml      "Restart <service-key> container" handlers (kolla_docker recreate_or_restart_container)
  tasks/main.yml         - include_tasks: "{{ kolla_action }}.yml"          <-- dynamic dispatch
  tasks/deploy.yml       register.yml → config.yml → check-containers.yml → bootstrap.yml → flush_handlers
  tasks/reconfigure.yml  - import_tasks: deploy.yml                          <-- reconfigure == deploy
  tasks/upgrade.yml      service-specific (stop/rolling, DB migrations, check-containers, flush)
  tasks/deploy-containers.yml  - import_tasks: check-containers.yml
  tasks/pull.yml         import_role: service-images-pull
  tasks/stop.yml         import_role: service-stop
  tasks/precheck.yml     import_role: service-precheck + port checks
  tasks/check.yml        (usually empty)
  tasks/config.yml       (also run alone for kolla_action=config, i.e. `genconfig`)
  tasks/config_validate.yml  import_role: service-config-validate (kolla_action=config_validate, `validate-config`)
  tasks/copy-certs.yml   import_role: service-cert-copy (from config.yml, when CA copy or backend TLS is enabled)
  tasks/loadbalancer.yml import_role: loadbalancer-config (tags: always)  <-- called from the loadbalancer play
  templates/             <service>.json.j2 (kolla_set_configs manifest), <svc>.conf.j2, …
```

There is no `meta/main.yml` any more: no role in `ansible/roles/` has a `meta/` directory [CODE]. Evidence for glance:
`roles/glance/tasks/main.yml`, `deploy.yml:2-15`, `reconfigure.yml:2`, `pull.yml`, `precheck.yml:2-6`,
`config.yml:38-40`, `loadbalancer.yml`; for nova: `roles/nova/tasks/deploy.yml`, `config_validate.yml`,
`vars/main.yml`.

### 4.1 `kolla_action` dispatch

`tasks/main.yml` is a **dynamic** `include_tasks: "{{ kolla_action }}.yml"`. Two consequences follow [CODE]:

- **`--list-tasks` is blind to role internals.** It shows only the `include_tasks` placeholder of every role: the
  listing walks the statically compiled play and does not load dynamically included files (ansible-core 2.14.18
  `lib/ansible/cli/playbook.py:202-207`; dynamic includes are loaded at run time,
  `lib/ansible/plugins/strategy/linear.py:291`).
  You cannot use `--list-tasks` to see what a tag will do in Kolla-Ansible. The linked
  [list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt) is the Ussuri parse; it shows the same placeholders.
- **Tags reach the role's tasks only through inheritance.** The included tasks inherit the *role and play* tags (e.g.
  `nova`), not tags written on the `include_tasks` statement itself (see [Tags
  §2](../risk/tags.md#2-ansible-29-semantics-that-kolla-relies-on)). An include is not statically loaded, so the block
  of included tasks skips the include's tags and inherits those of the role, its dependency chain and the play
  (ansible-core 2.14.18 `lib/ansible/playbook/task_include.py:50`, `lib/ansible/playbook/block.py:313-361`).

### 4.2 `reconfigure` is `deploy`

Of the 59 roles that have a `reconfigure.yml`, 56 only do `import_tasks: deploy.yml`. `skyline` does the same with
`include_tasks`. `swift` and `bifrost` have their own reconfigure logic: swift fails if a container is down, runs
`kolla_set_configs --check` and restarts only drifted containers (`roles/swift/tasks/reconfigure.yml:32-50` and
following).

The bifrost copy cannot work and no `kolla-ansible` command runs it: it uses a group and a container named
`bifrost-deploy` (`roles/bifrost/tasks/reconfigure.yml:2-23`), but the container is `bifrost_deploy`
(`roles/bifrost/tasks/start.yml:8`), the example inventory has no `bifrost-deploy` group, `roles/bifrost/templates/`
holds no `config.json` template, and the wrapper sends `reconfigure` to `site.yml`, which has no bifrost play
(`tools/kolla-ansible:515-518`).

See the generated column "reconf→deploy" in [Generated inventory
§3](../reference/generated-inventory.md#3-role-task-structure-handlers-and-helper-role-usage). So `reconfigure` re-runs
Keystone registration, DB creation and the **bootstrap (DB sync) container** of most services, exactly like `deploy`
[CODE] (e.g. `roles/glance/tasks/reconfigure.yml:2`, `roles/glance/tasks/deploy.yml:2-15`). The only built-in
differences between `deploy` and `reconfigure` are:

- **`kolla_serial`** is passed from `ANSIBLE_SERIAL` ([§2](#2-from-cli-to-ansible-playbook)).
- **No `when: kolla_action == ...` condition separates them any more.** Every condition in `ansible/` that names
  `deploy` or `reconfigure` names both (`nova.yml:51, :87, :156`; `mariadb.yml:66`; `rabbitmq.yml:55, :111`;
  `site.yml:341`). The Ussuri example is gone: Neutron's DB-sync container (`bootstrap_neutron`) is imported without
  any condition (`roles/neutron/tasks/bootstrap.yml:38`, `roles/neutron/tasks/bootstrap_service.yml:2-21`), so it runs
  on every `deploy` and `reconfigure`; `neutron_enable_rolling_upgrade` (`roles/neutron/defaults/main.yml:710`) is
  now read only by `roles/neutron/tasks/upgrade.yml:5, :8`. Nova's bootstrap plays run on both `deploy` and
  `reconfigure` (`ansible/nova.yml:47-51, :83-87`).

### 4.3 The config → check → handler pattern

This is the heart of Day-2 behaviour:

```mermaid
sequenceDiagram
  autonumber
  participant DH as Deploy host (ansible-playbook)
  participant H as Target host
  participant C as Container
  DH->>DH: render template / merge_configs locally (Jinja + INI merge)
  DH->>H: copy module: compare checksum of /etc/kolla/<svc>/<file>
  alt content differs
    DH->>H: write file (changed) → notify "Restart <svc> container"
  end
  DH->>H: kolla_docker compare_container (check-containers.yml)
  H->>C: docker inspect (image id/tag, volumes, env, privileged, pid/ipc/cgroupns, caps, dimensions, labels, command, healthcheck, state)
  H->>C: docker exec kolla_set_configs --check (config drift between /var/lib/kolla/config_files and live files)
  H->>H: compare /etc/systemd/system/kolla-<name>-container.service with the unit it would write
  alt differs or drift
    DH-->>DH: notify "Restart <svc> container"
  end
  Note over DH,H: meta: flush_handlers (end of deploy.yml) or end of play
  DH->>H: handler: kolla_docker recreate_or_restart_container
  alt image or container params differ
    H->>C: pull image if absent → systemd stop (docker stop -t 60) → rm → create + unit → systemd start  (RECREATE)
  else only config changed (COPY_ALWAYS)
    H->>C: rewrite unit if needed → systemd RestartUnit (docker stop -t 60, docker start)  (RESTART)
  end
```

- **Files are rendered on the deploy host and copied.** The `template` and `merge_configs` steps render on the deploy
  host, then the `copy` logic compares checksums on the target. So *every* config task costs one SSH round trip per host
  per item, even when nothing changes (see [Compute scaling](compute-scaling-and-performance.md)).
- **Three independent triggers lead to the same handler.** A changed file notifies directly. The `compare_container`
  task (`module_utils/kolla_container_worker.py:59-66`) also notifies when:
  - the container's definition differs (`check_container_differs`, `kolla_container_worker.py:68-90`: capabilities,
    security options, image ID or tag, ipc/pid/cgroupns mode, labels, privileged, tmpfs, volumes, environment, state,
    dimensions, command, healthcheck); or
  - **`kolla_set_configs --check`** inside the running container reports drift
    (`module_utils/kolla_docker_worker.py:155-190`; a container that cannot be exec'd into counts as drifted,
    `:164-171`); or
  - the container's systemd unit file is missing or differs from the one the module would write
    (`module_utils/kolla_systemd_worker.py:149-162`), for example after `docker_graceful_timeout`,
    `docker_restart_policy` or `docker_client_timeout` changed, since all three are written into the unit
    (`kolla_systemd_worker.py:20-40, :50-74`).

  The `--check` path means a config file changed by an earlier `genconfig`, or by hand, will still restart the
  container on the next `deploy`/`reconfigure`/`deploy-containers` [CODE].
- **Restart and recreate are both full stop/start cycles.** A config change is applied only by stopping and starting
  the container; `kolla_docker` has no reload action (`library/kolla_docker.py:263-279`). The only signal
  Kolla-Ansible sends to a running containerised service is SIGHUP to `nova_scheduler` (cell-cache refresh), through
  `kill -HUP` on the PID read with `{{ kolla_container_engine }} inspect`. It is sent only on a `deploy`/`reconfigure`
  that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag (or no tag) and whose `--limit`, if any,
  includes the `nova-scheduler` hosts (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10-12`,
  `ansible/nova.yml:140-156`). It loads no new config files. (Outside containers, the `Reload libvirtd` handler
  reloads a *host* libvirtd when the external-Ceph tasks change its secrets and `enable_nova_libvirt_container` is
  false, `roles/nova-cell/handlers/main.yml:142-148`, `roles/nova-cell/tasks/external_ceph.yml:191-194`.) The handler
  calls `recreate_or_restart_container` (`module_utils/kolla_docker_worker.py:362-384`):
  - **recreate** when the image or parameters differ (or `COPY_ONCE`): pull the image if absent, stop, remove, start;
  - otherwise **restart**: rewrite the unit if needed and ask systemd to restart it (`restart_container`,
    `:460-480`; `kolla_systemd_worker.py:101-108`).

  The stop timeout is **`docker_graceful_timeout`, 60 s by default**
  ([§6](#6-custom-modules--container-lifecycle-via-kolla_docker)).
- **Handlers run in definition order, on every notified host of the batch at once.** Unless `kolla_serial` is set,
  "Restart nova-compute container" restarts nova_compute on all notified computes in the same step [CODE: ansible-core
  2.14.18 `lib/ansible/executor/play_iterator.py:197` copies the play's handlers in definition order and `:430-453`
  walks them per host; the linear strategy runs the handler phase in lockstep across the hosts of the batch,
  `lib/ansible/plugins/strategy/linear.py:78-123`].

### 4.4 Containers and placement

Each role's `defaults/main.yml` defines a `<role>_services` dict with an entry per container. The fields are
`container_name`, `group` *or* `host_in_groups`, `enabled`, `image`, `volumes`, `dimensions`, `privileged`,
`pid_mode`/`ipc_mode`/`cgroupns_mode`, `healthcheck` and `haproxy`. The filter `service_enabled_and_mapped_to_host`
(`kolla_ansible/filters.py:59-96`) decides placement:

- `host_in_groups` (a per-host boolean expression) wins over `group` (`filters.py:75-77`).
- `group: all` means every host (`filters.py:79-81`).

`select_services_enabled_and_mapped_to_host` (`filters.py:99-109`) applies the same test to a whole dict; the helper
roles `service-images-pull`, `service-config-validate` and others loop over its result.

All 188 container definitions are listed in [Generated inventory
§2](../reference/generated-inventory.md#2-containers-defined-by-each-role-role_services-in-defaultsmainyml).

---

## 5. Shared helper roles

| Role | Used by | What it does | Scope |
|---|---|---|---|
| `common` | its own play (`site.yml:86-97`); no role depends on it | Deploys `fluentd`, `kolla_toolbox`, `cron` on the hosts of their groups (children of `common`: every host of the example inventory). Renders `td-agent.conf` and `logrotate.conf` | Once per host per run that executes the `common` play ([§5.1](#51-the-common-role-and-the-common_run-guard)) |
| `service-ks-register` | 37 roles | Creates the Keystone service, endpoints, project, user, role and grants through `kolla_toolbox` | `run_once`: once per play, or once per batch when `kolla_serial` is set (`roles/service-ks-register/tasks/main.yml:136`) |
| `service-rabbitmq` | nova-cell only (`roles/nova-cell/tasks/rabbitmq.yml`, imported from `bootstrap.yml:37`) | Creates RabbitMQ vhost and user through `kolla_toolbox`, delegated to the first host of the cell's RPC (or notify) RabbitMQ group | once per cell, on the cell's first nova-conductor host (the notify pass only when its group or users differ from RPC) |
| `service-images-pull` | the `pull.yml` of 55 roles | `kolla_docker pull_image` for every enabled container mapped to the host, with retries (`roles/service-images-pull/tasks/main.yml`) | per host × per container |
| `service-stop` | the `stop.yml` of 56 roles | `kolla_docker stop_container`, honouring `skip_stop_containers` | per host × per container |
| `service-precheck` | the `precheck.yml` of 54 roles | Validates that the inventory groups exist | per host |
| `service-cert-copy` | `copy-certs.yml` of 43 roles | Copies the CA (and backend certs) into each service config dir when `kolla_copy_ca_into_containers` or the service's backend TLS is set (e.g. `roles/glance/tasks/config.yml:38-40`) | per host × per service |
| `service-config-validate` | `config_validate.yml` of 34 roles | `validate-config`: runs the oslo-config validator for each enabled service mapped to the host (`roles/service-config-validate/tasks/main.yml`) | per host × per service |
| `loadbalancer-config` | every role's `loadbalancer.yml` (44 roles) | Imports `haproxy-config` (when `haproxy_config_install`) and `proxysql-config` (when `enable_proxysql`) (`roles/loadbalancer-config/tasks/main.yml:2-8`) | per loadbalancer host |
| `haproxy-config` | `loadbalancer-config` only | Renders `/etc/kolla/haproxy/services.d/<svc>.cfg` (custom templates under `/etc/kolla/config/haproxy-config/` win) and opens external ports in firewalld when enabled (`roles/haproxy-config/tasks/main.yml:2-41`) | per loadbalancer host |
| `proxysql-config` | `loadbalancer-config` only | Renders the ProxySQL users and rules files for the service | per loadbalancer host |
| `module-load` | nova-cell (`br_netfilter`), neutron, openvswitch, loadbalancer, ironic, iscsi (`configfs`), multipathd, from each role's `config-host.yml` | `modprobe` and persistence in `/etc/modules-load.d` | per host |

### 5.1 The `common` role and the `common_run` guard

The guard no longer exists. `roles/common/tasks/main.yml:1-2` is now only:

```yaml
- include_tasks: "{{ kolla_action }}.yml"
```

No file in `ansible/` or `tools/` mentions `common_run`, and `roles/common/defaults/main.yml` starts directly with
`common_services` [CODE]. What replaced it:

- **`common` runs in one play of its own** (`site.yml:86-97`: hosts `cron`, `fluentd`, `kolla-logs`,
  `kolla-toolbox`; `serial: kolla_serial`; play tag `common`). It runs before the loadbalancer play and before any
  service play, on every host of those groups, once per run.
- **`-t common` selects that play and nothing else.** The included tasks inherit the play tag `common` (ansible-core
  2.14.18 `lib/ansible/playbook/block.py:313-361`, `lib/ansible/plugins/strategy/linear.py:311`), so
  `-t common reconfigure` renders the common configs and restarts what changed [CODE]. The Ussuri behaviour, where it
  rendered and restarted nothing, is gone.
- **Service tags no longer drag `common` in.** No role has a `meta/` directory, so `-t nova` (or any service tag)
  skips the common play, which carries only `common`
  [CODE; [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)]. The Ussuri behaviour, where
  `-t nova` ran the whole `common` role on every nova host, computes included, is gone.
- **`fluentd` and `cron` configs are global.** `td-agent.conf` and `logrotate.conf` are rendered from the **global**
  `enable_*` flags (`roles/common/tasks/config.yml:76-209`). Enabling a service listed in
  `fluentd_input_openstack_services` (`roles/common/defaults/main.yml:138-202`) and/or `cron_logrotate_services`
  (`roles/common/tasks/config.yml:138-209`), such as nova, neutron or barbican, changes `td-agent.conf` and/or
  `logrotate.conf` on *every* host. Services only in the logrotate list (e.g. mariadb, rabbitmq, zun, vitrage,
  placement, prometheus) change only `logrotate.conf`, and some flags change neither file (e.g. `enable_redis`,
  `enable_memcached`, `enable_ovn`).

  Since `common` no longer runs with a service tag, enabling a service with `-t <svc> deploy` does **not** update
  these files; they change on the next run that executes the common play (a full run or `-t common`). That run
  restarts the container whose file changed (`fluentd` and/or `cron`). Through loop-notify on the looped
  `Check common containers` task (`roles/common/tasks/check-containers.yml:2-17`) it also restarts the other common
  containers (`kolla_toolbox`, plus `fluentd` or `cron` when only one of the two files changed), although their config
  did not change [CODE: when any item of a looped task changes, Ansible notifies the handlers of every item that was not
  skipped, ansible-core 2.14.18 `lib/ansible/executor/task_executor.py:124-128, :804-805`,
  `lib/ansible/plugins/strategy/__init__.py:614-621`; see [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)].

---

## 6. Custom modules — container lifecycle via `kolla_docker`

| Module | Purpose | Key behaviour (evidence) |
|---|---|---|
| `kolla_docker` (`ansible/library/kolla_docker.py`, 416 lines, plus `module_utils/kolla_docker_worker.py` 524, `kolla_container_worker.py` 570, `kolla_systemd_worker.py` 211) | Every container lifecycle operation of the service roles (390 `kolla_docker:` tasks under `ansible/roles/`) | Actions: `compare_container`, `compare_image`, `create_volume`, `ensure_image`, `get_container_env`, `get_container_state`, `pull_image`, `recreate_or_restart_container`, `remove_container`, `remove_image`, `remove_volume`, `restart_container`, `start_container`, `stop_container`, `stop_and_remove_container` (`kolla_docker.py:263-279`). Uses host networking (`kolla_docker_worker.py:286-288`). Docker only: the module imports only `DockerWorker` (`kolla_docker.py:22`) and the unit template calls `/usr/bin/docker` (`kolla_systemd_worker.py:32-33`). Every non-oneshot container gets a systemd unit `kolla-<name>-container.service` that starts, stops and restarts it ([below](#how-kolla_docker-decides)) |
| `kolla_toolbox` (`library/kolla_toolbox.py`) | Runs an Ansible module *inside* the `kolla_toolbox` container (`exec_create` of `ansible localhost -m <module>`, `kolla_toolbox.py:115-116, :182, :219`) | Used for MySQL, Keystone (`os_*`) and RabbitMQ (`rabbitmq_user/vhost`) operations. Takes a required `container_engine` parameter (`:147`). Needs a running `kolla_toolbox` on the target |
| `kolla_container_facts` | Returns the running containers by name; takes `container_engine` | Used by prechecks and upgrade logic (e.g. `roles/glance/tasks/precheck.yml:8-12`) |
| `kolla_container_volume_facts` | Returns container volume facts | New in 2023.1; used by `roles/neutron/tasks/neutron_plugin_agent_check.yml` and `roles/ovn-db/tasks/lookup_cluster.yml` |

The Ussuri `bslurp` module is gone from `ansible/library/`. Swift rings are copied with `copy` from
`{{ node_custom_config }}/swift` (`roles/swift/tasks/config.yml`), and Fernet keys are distributed by `fernet-push.sh`,
run with `{{ kolla_container_engine }} exec` in the keystone_fernet container
(`roles/keystone/tasks/distribute_fernet.yml:14`).

These modules are not the only container interface. Many role tasks call the container CLI directly through
`command`/`shell` as `{{ kolla_container_engine }} exec|inspect` (20 roles, among them keystone, mariadb, rabbitmq,
openvswitch, ovn-db, nova-cell, swift and bifrost): `fernet-push.sh`, `ovs-vsctl`, `kolla_set_configs --check`
(swift, bifrost), the `mysql`/`rabbitmqctl` calls of the MariaDB and RabbitMQ roles (e.g.
`roles/mariadb/tasks/restart_services.yml:34`), and `inspect` plus `kill -HUP` for `nova_scheduler`. Outside the
service roles, `destroy` stops and removes containers with the `tools/cleanup-containers` script, passing the engine
(`roles/destroy/tasks/cleanup_containers.yml:3`; the script accepts `docker` or `podman`,
`tools/cleanup-containers:4-10`); `prune-images` uses the `docker_prune` module
(`roles/prune-images/tasks/prune_images.yml:2-8`), which is not part of ansible-core 2.14.18 (`lib/ansible/modules/`
has no docker module) and is not in `requirements.yml`, so it must come from the operator's Ansible installation
[CODE]; and `bootstrap-servers` runs `docker start` on the previously running containers after a Docker package
upgrade (ansible-collection-kolla `roles/docker/tasks/install.yml:44-72`) [CODE].

<a id="how-kolla_docker-decides"></a>How `kolla_docker` decides [CODE]:

- **`start_container`** pulls the image **only if it is absent locally**
  (`module_utils/kolla_docker_worker.py:386-388`).
  A rebuilt image pushed under the same tag is therefore *not* fetched by `deploy` or `reconfigure`. It takes an
  explicit `pull` (`kolla-ansible pull`) to download it, after which `compare_image` sees a new image ID and recreates
  the container (`kolla_docker_worker.py:116-131, :362-384`). It then creates the container and its unit if needed and
  starts it through systemd, failing with "Container timed out" if the unit is not `running` within
  `client_timeout` (120 s) (`:386-410`; `kolla_systemd_worker.py:92-99, :200-211`). One-shot containers
  (`restart_policy: oneshot`) get no unit and are started directly (`:402-403`).
- **`compare_image` compares image ID and tag**, using the local image for that reference
  (`kolla_docker_worker.py:116-131`).
- **`pull_image` reports changed only if the local image ID changed** (`kolla_docker_worker.py:198-232`).
- **`docker_graceful_timeout` and `docker_client_timeout` now take effect.**
  - `generate_module()` starts from `common_options` (= `docker_common_options`, which carries
    `graceful_timeout: "{{ docker_graceful_timeout }}"` and `client_timeout: "{{ docker_client_timeout }}"`,
    `group_vars/all.yml:140-153`). It overwrites a key only when the task sets that parameter; a parameter the task
    leaves unset keeps the `common_options` value, and only when that is absent too does the module default (10 s and
    120 s) apply (`kolla_docker.py:351-382`).
  - `graceful_timeout` and `client_timeout` have no default in the argument spec any more (`kolla_docker.py:303, :325`).
    Handlers pass `common_options` (e.g. `roles/nova-cell/handlers/main.yml:74-168`), so the effective stop timeout
    is `docker_graceful_timeout`, **60 s** by default (`group_vars/all.yml:140`).
  - The value is written into the unit: `ExecStop=/usr/bin/docker stop <name> -t <graceful_timeout>`
    (`kolla_systemd_worker.py:33, :69`). `stop_container` uses systemd when the unit exists and `docker stop` with the
    same timeout otherwise (`kolla_docker_worker.py:436-452`); `restart_container` asks systemd to restart the unit
    (`:460-480`).
  - Practical effect: a container still running 60 s after SIGTERM is killed. This holds for handler restarts,
    recreates and `stop` [CODE; the SIGTERM-then-SIGKILL meaning of the timeout is kolla-ansible's own comment,
    `ansible/group_vars/all.yml:139`: "Timeout after Docker sends SIGTERM before sending SIGKILL."]. The unit sets no
    `TimeoutStopSec`, so systemd's own stop timeout also applies; its value is host configuration [NOT AVAILABLE].
- **The restart policy lives in the unit, not in Docker.** `build_host_config` passes no restart policy to Docker
  (`kolla_docker_worker.py:286-321`); `docker_restart_policy: "unless-stopped"` (`group_vars/all.yml:117`) becomes
  `Restart=always` in the unit, with `StartLimitBurst` = `docker_restart_policy_retry` (`kolla_systemd_worker.py:26-34,
  :50-74`). The FIXME "restart_policy is *not* checked in the container" (`kolla_docker_worker.py:15`) remains, but a
  changed policy changes the unit, which `compare_container` does detect
  ([§4.3](#43-the-config--check--handler-pattern)).
- **`kolla_container_engine` is not an engine switch for the lifecycle.** It defaults to `"docker"`
  (`group_vars/all.yml:92`) and is substituted into CLI calls and passed to `kolla_toolbox` and the facts modules, but
  `kolla_docker` only drives Docker and no file under `ansible/` mentions `podman` [CODE].

---

## 7. Configuration generation and overrides

1. **INI files go through `merge_configs`.** `merge_configs` (`ansible/action_plugins/merge_configs.py`) renders each
   listed source as a Jinja template *on the deploy host*, merges them as INI (later sources win), then calls the
   `copy` action. For nova-compute the sources are (`roles/nova-cell/tasks/config.yml:69-89`):
   `templates/nova.conf.j2` → `/etc/kolla/config/global.conf` → `/etc/kolla/config/nova.conf` →
   `/etc/kolla/config/nova/nova-compute.conf` → `/etc/kolla/config/nova/<inventory_hostname>/nova.conf`.
2. **Overrides are scoped by file location.** Putting a value into `/etc/kolla/config/nova.conf` affects **every nova
   container that has a `nova.conf` on every host** (nova-api, scheduler, super-conductor, conductor, novncproxy and
   every nova-compute). The content of `/etc/kolla/config/nova/nova-compute.conf` is merged only into nova-compute's
   `nova.conf`, so the control-plane nova services are untouched [CODE: the `nova` and `nova-cell` roles each merge
   `nova/<service>.conf` only into that service's own `nova.conf`, `roles/nova/tasks/config.yml:64-82`,
   `roles/nova-cell/tasks/config.yml:69-89`, `roles/nova/defaults/main.yml:2-57`,
   `roles/nova-cell/defaults/main.yml:478-484`]. Operationally, `-t nova reconfigure` after changing it still restarts
   `nova_compute`, `nova_libvirt` and `nova_ssh` on every compute host [CODE]. The changed file makes
   `kolla_set_configs --check` report drift in `nova_compute` (`module_utils/kolla_docker_worker.py:155-190`).
   libvirt and ssh restart through loop-notify in the looped "Check nova-cell containers" task
   (`roles/nova-cell/tasks/check-containers.yml:2-22`, handlers `roles/nova-cell/handlers/main.yml:74-168`; Ansible
   lines in [§5.1](#51-the-common-role-and-the-common_run-guard)), not because their config changed.
3. **Some overrides leak to other services.** In Ussuri, Neutron's `openvswitch_agent.ini` merged
   `/etc/kolla/config/neutron/ml2_conf.ini`. In 2023.1 it no longer does: `ml2_conf.ini` (template plus
   `neutron/ml2_conf.ini` overrides) is rendered only for `neutron-server` and `neutron-infoblox-ipam-agent`
   (`roles/neutron/tasks/config.yml:158-178`), and `openvswitch_agent.ini` merges only its own template and
   `neutron/openvswitch_agent.ini` overrides (`:197-206`). A change meant for `neutron-server` therefore no longer
   restarts `neutron_openvswitch_agent` [CODE; [Reconfigure Neutron](../operations/reconfigure-neutron.md)]. The
   file-location scoping of point 2 is still the rule: `/etc/kolla/config/neutron.conf` or `global.conf` reach every
   container whose template merges them.
4. **The container receives its config through a manifest.** The `config.json` (rendered from `<service>.json.j2`) tells
   `kolla_set_configs`, inside the image, which files to copy from `/var/lib/kolla/config_files` (bind-mounted from
   `/etc/kolla/<service>/`) to their final location. It also names the command to start. With `config_strategy:
   COPY_ALWAYS` (`group_vars/all.yml:43`) the copy happens at every container start. That is why a restart is enough to
   apply a changed or added config file, and why Kolla-Ansible never applies config by reloading a service.

   In 2023.1 a restart also applies most removals [CODE]. Before copying, `kolla_set_configs` (kolla 2023.1-eol)
   reads a state file kept inside the container, `/etc/kolla/defaults/state`, and for every destination it has ever
   written either restores the image's original file (saved under `/etc/kolla/defaults/`) or deletes it when the image
   had none; it then records any new destinations (kolla `docker/base/set_configs.py:32-33, :452-474, :477-513,
   :516-532, :535-553`). So a file whose entry was dropped from `config.json` (e.g. a removed Keystone policy file,
   `roles/keystone/templates/keystone.json.j2:31-37`), or whose optional source is gone (the copy then skips it,
   `set_configs.py:143-145`), returns to the image default or disappears at the next start. Limits:
   - The state lives in the container's own filesystem, so a **recreate** starts with an empty state. A stale file on a
     **named volume** (e.g. nova-compute's SASL `auth.conf` under `/var/lib/nova`,
     `roles/nova-cell/templates/nova-compute.json.j2:58-61`) whose entry was dropped is then neither restored nor
     deleted.
   - `kolla_set_configs --check` compares only the entries of the current `config.json`
     (`set_configs.py:556-559, :220-243`), so a dropped entry alone does not report drift; the restart comes from the
     changed `config.json` file itself.
   - Deleting a custom file such as `/etc/kolla/config/keystone/keystone-paste.ini` leaves its rendered copy in
     `/etc/kolla/keystone/` (`roles/keystone/tasks/config.yml:169-193`), and the optional manifest entry
     (`keystone.json.j2:18-24`) keeps copying it in, even after a recreate.

   The image-side start path and `--check` are described in [Kolla images
   §2-§3](kolla-images.md#2-start-path-common-to-every-image).

---

## 8. Inventory model

- **Groups are mostly aliases of a few physical groups.** The physical groups are `control`, `network`, `compute`,
  `storage`, `monitoring` and `deployment` (`ansible/inventory/multinode:3-33`). Service groups are defined as
  children. Examples:
  - `[nova-api:children] nova`, `[nova:children] control` (`multinode:263-264, :117-118`).
  - `[loadbalancer:children] network` (`multinode:86-87`). In the 2023.1 example inventory, HAProxy and keepalived
    sit on the **network** nodes; there is no `haproxy` group any more.
  - `[openvswitch:children] network, compute, manila-share` (`multinode:123-126`).
  - `[common:children]` = control, network, compute, storage, monitoring, and `cron`, `fluentd`, `kolla-logs`,
    `kolla-toolbox` are children of `common` (`multinode:48-53, :239-249`).
- **Groups that include `compute` in the example inventory** (33 in total, counted from `ansible/inventory/multinode`):
  - `compute` itself and the groups that list it directly as a child: `baremetal`, `common`, `collectd`, `telegraf`,
    `hacluster-remote`, `monasca-agent`, `openvswitch`, `cyborg`, `neutron-ovn-metadata-agent`, `neutron-ovn-agent`,
    `iscsid`, `ceilometer-compute`, `ceilometer-ipmi`, `cyborg-agent`, `multipathd`, `zun-compute`, `zun-cni-daemon`,
    `prometheus-node-exporter`, `prometheus-cadvisor`, `prometheus-libvirt-exporter`, `masakari-instancemonitor`,
    `ovn-controller-compute`.
  - Through nesting: `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` (via `common`), `cyborg-api` and
    `cyborg-conductor` (children of `cyborg`, which is control + compute, so they also land on compute hosts),
    `monasca-agent-collector`, `monasca-agent-forwarder` and `monasca-agent-statsd` (via `monasca-agent`), and
    `ovn-controller` (via `ovn-controller-compute`).
- **The neutron play also targets every compute host.** It lists `compute` and `manila-share` explicitly
  (`site.yml:590-608`); the agents' `host_in_groups` decides what lands there.
- **Inventory order is semantically significant** [CODE]. `groups['<grp>'][0]` is the target of almost every
  `run_once`/`delegate_to` bootstrap step. Examples: `groups[nova_cell_conductor_group][0]` for cell creation and
  compute discovery (`roles/nova-cell/tasks/bootstrap.yml:15, :34`); the first `glance-api` host as the only glance
  host with the default file backend (`group_vars/all.yml:915`; [fact sheet
  C](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md)). Other index-sensitive logic:
  - keepalived priority is the index in `groups['loadbalancer']` plus 1
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`; [fact sheet A
    §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour) C);
  - HAProxy's single active MariaDB backend is the first host of the default shard, the others being `backup`
    (`roles/mariadb/defaults/main.yml:64`). The Ussuri modulo-4 restart waves are gone: MariaDB restarts in the
    `serial: "33%"` batches of the `Restart mariadb services` play (`mariadb.yml:14-26`); in which batch the active
    backend restarts is [NOT AVAILABLE] ([R9](../risk/risk-register.md#r9); [fact sheet B §1.5][sheet-b-15]).

## Related

- [Tags](../risk/tags.md) (how tags select this work)
- [Execution flow](deployment-execution-flow.md) (execution order and the action matrix)
- [Generated inventory](../reference/generated-inventory.md) (every play, container, role and handler)
- [Tag index](../risk/tag-index.md), [Components](../components/index.md) and [Glossary](../reference/glossary.md) (tag
  index, service index, glossary)

[sheet-b-15]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order

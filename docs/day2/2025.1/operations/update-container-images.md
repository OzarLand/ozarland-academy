---
title: Update container images
description: How pull, deploy, reconfigure and upgrade treat images in 2025.1 (Docker and Podman), what is recreated, the risks of a tag change with deploy, prune-images.
tags: [images, pull, deploy, upgrade, podman, nova, neutron, openvswitch, serial, one-shot]
impact: [pulls-images, recreates-containers, critical]
---

# Update container images

How `kolla-ansible pull`, `deploy`, `reconfigure` and `upgrade` treat container images in 2025.1, with the Docker and
the Podman back ends: `pull` never changes running containers, and after a `pull` that downloaded something the next
`deploy`, `reconfigure` or `upgrade` recreates the affected containers. The page also covers `prune-images`.

The image counts per host in [§2](#2-how-image-pulling-and-recreation-work-code) are for the service set of the [assumed
deployment](index.md#assumed-deployment).

> [!NOTE]
> **Key answers**
>
> - **Images ([§2 to §5](#2-how-image-pulling-and-recreation-work-code)):** a `deploy` without `pull` does not download
>   a rebuilt image, and a new `openstack_tag` applied with `deploy` recreates every container on every host [CODE]
>   ([§2](#2-how-image-pulling-and-recreation-work-code)). Risks of doing so: [§4](#4-risks).
> - **Images:** `pull` never changes running containers, and `deploy`/`reconfigure` never pull an image that is already
>   present locally [CODE] ([§1.1](#11-images)). Both still hold in 2025.1, for the Docker and the Podman worker.
> - **Changed in 2025.1** [CODE]: only the container whose image changed is recreated (no loop-notify any more); the
>   common play no longer pulls the fluentd image; `upgrade` always runs with `kolla_serial=0`, so it can be split
>   only with `--limit` ([§1.1](#11-images)).

> [!CAUTION]
> [R12](../risk/risk-register.md#r12): changing the tag and running `deploy` (instead of `upgrade`) recreates the whole
> fleet in one go, without the upgrade-specific ordering — see [§4](#4-risks).

## 1. Commands

### 1.1 Images

```bash
kolla-ansible pull -i multinode                          # all enabled images on all hosts
kolla-ansible pull -i multinode -t nova --limit compute  # nova-cell images on computes (common images: add -t common)
kolla-ansible upgrade -i multinode                       # recreate from new images (after pull)
kolla-ansible upgrade -i multinode -t nova --limit 'compute[0:19]'   # split by host: kolla_serial cannot batch upgrade
```

- `pull` runs `site.yml` with `kolla_action=pull` (`kolla_ansible/cli/commands.py:173-184`). It never changes running
  containers [CODE]: the only task of `service-images-pull` runs `kolla_container` `pull_image` for each enabled
  container mapped to the host and notifies no handler (`roles/service-images-pull/tasks/main.yml:2-18`). With Docker,
  `pull_image` pulls the `repository:tag` and reports changed only when the local image ID of that reference changed
  (`module_utils/kolla_docker_worker.py:197-231`); with Podman, when the image attributes changed
  (`module_utils/kolla_podman_worker.py:554-573`).
- `deploy`/`reconfigure` never pull an image that is already present locally, even if the registry has a newer
  build under the same tag [CODE]. With Docker, `check_image` looks the `repository:tag` up among the local images
  (`module_utils/kolla_docker_worker.py:71-79`), and `start_container` and `recreate_or_restart_container` pull only
  when it is missing (`:364-369, :376-378`). With Podman, `check_image` asks the engine for the local image of that
  name, and both paths go through `ensure_image`, which pulls only an absent image
  (`module_utils/kolla_podman_worker.py:263-276, :618-619, :628-629, :789-791`).
- **Changed in 2025.1:** the common play no longer pulls anything at its config step: the 2024.1 `ensure_image` on the
  fluentd image is gone (`roles/common/tasks/config.yml` has no `kolla_container` task; it now installs
  `kolla.target`, `:54-58`). In `deploy`, `reconfigure` and `upgrade`, the RabbitMQ version check still starts a
  one-shot container from the configured rabbitmq image once the `rabbitmq` container exists
  (`roles/rabbitmq/tasks/version-check.yml:19-37, :76`; `roles/rabbitmq/tasks/reconfigure.yml:2`), and
  `start_container` pulls an absent image first; **new in 2025.1**, the nova-cell role does the same with the
  `nova_libvirt` image on the first compute (`roles/nova-cell/tasks/version-check.yml:3-21, :80-98`).
- After a `pull` that downloaded something, the next `deploy`, `reconfigure` or `upgrade` **recreates** the affected
  containers. **Changed in 2025.1:** only those, not their siblings: the shared check step notifies the handler of each
  changed container only [CODE `module_utils/kolla_container_worker.py:58-89`,
  `module_utils/kolla_docker_worker.py:107-122, :352-374`, `module_utils/kolla_podman_worker.py:360-378, :609-626`,
  `roles/service-check-containers/tasks/main.yml:4-41`; [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)].
- `library/kolla_container.py` parses the arguments and picks `DockerWorker` when `container_engine` is `docker`,
  `PodmanWorker` otherwise (`library/kolla_container.py:411-416`); the engine comes from `docker_common_options`
  (`group_vars/all.yml:162`), and `kolla_container_engine` defaults to `docker` (`group_vars/all.yml:100`). The logic is
  in `module_utils/kolla_container_worker.py`, `module_utils/kolla_docker_worker.py` and
  `module_utils/kolla_podman_worker.py` ([Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)).
- **Changed in 2025.1, batching:** `upgrade` and `reconfigure` always pass `kolla_serial=0` after the user's `-e`
  (`kolla_ansible/cli/commands.py:20-22, :136, :278`; [F19](../reference/findings.md#f19)); the `ANSIBLE_SERIAL`
  environment variable of 2024.1 is no longer read. With `pull` and `deploy`, `-e kolla_serial=N` works: the plays that
  set `serial: kolla_serial` then run their hosts in batches (default `"0"`, one batch, e.g. `site.yml:95`,
  `nova.yml:140`); the MariaDB and RabbitMQ restart plays keep their fixed `serial: "33%"` (`mariadb.yml:24`,
  `rabbitmq.yml:36`). To split an `upgrade`, use `--limit`.

### 1.2 Prune old images

```bash
kolla-ansible prune-images -i multinode --yes-i-really-really-mean-it
```

- The command refuses to run without `--yes-i-really-really-mean-it` and runs `prune-images.yml`
  (`kolla_ansible/cli/commands.py:362-381`) [CODE].
- The playbook imports `gather-facts.yml`, then applies the role `prune-images` to the `baremetal` hosts, with
  `serial: kolla_serial` (default `"0"`, one batch) and `max_fail_percentage` (`prune-images.yml:1-13`) [CODE].
  `baremetal` holds the control, network, compute, storage and monitoring groups, not the deploy host
  (`inventory/multinode:32-40`).
- The role first checks that `sudo <engine> ps` works (`roles/prune-images/tasks/validate_docker_execute.yml:2-5`,
  `tools/validate-docker-execute.sh:7-15`). Then it branches on the engine
  (`roles/prune-images/tasks/prune_images.yml:2-16`) [CODE]:
  - Docker: the `docker_prune` module with `images: yes`, the filter `label: kolla_version` and a timeout of
    `docker_image_prune_timeout` (300 s, `roles/prune-images/defaults/main.yml:2`). `docker_prune` is not an
    ansible-core module: ansible-core 2.18.20 redirects it to `community.docker.docker_prune`
    (`lib/ansible/config/ansible_builtin_runtime.yml:745-746`), which `requirements-core.yml:18-20` pins below 5;
    **changed in 2025.1**, `kolla-ansible install-deps` always installs that file (`kolla_ansible/ansible.py:307-318`).
  - Podman: `podman image prune --force --filter 'label=kolla_version'`, as a `command` task; the comment says that
    Podman has no equivalent of `docker_prune` and that `podman_image` has no label filter (`:11-16`).
  - Any other value of `kolla_container_engine` prunes nothing (both tasks are guarded by `when`).
- [NOT AVAILABLE] What either prune removes exactly: whether only dangling images go, and so whether the images of the
  previous release are kept after an upgrade, is the behaviour of the `community.docker` collection and of Podman, which
  are not in these sources. The kolla-ansible docs call the command a prune of "orphaned Docker images"
  (`doc/source/user/operating-kolla.rst:235-236`). `tools/cleanup-images --image-version <value>` removes, on the host
  where it runs, the images whose `kolla_version` label equals that value (`tools/cleanup-images:75-78, :94`); which
  value the images carry is [NOT AVAILABLE] here.

## 2. How image pulling and recreation work [CODE]

```mermaid
flowchart LR
  A["registry: new build"] -->|"kolla-ansible pull (service-images-pull)"| B["image present on host<br/>(pull_image: changed if the local image changed)"]
  A -.->|"deploy / reconfigure WITHOUT pull:<br/>image already present → NOT pulled"| X["no change"]
  B --> C["deploy / reconfigure / upgrade:<br/>service-check-containers compare_container → image ID differs"]
  C --> D["handler of that container only:<br/>recreate_or_restart_container: stop (systemd unit, docker_graceful_timeout 60 s) → rm → create → start"]
```

The diagram holds for both engines: `compare_container` is the same test in the Docker and the Podman worker
(`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_podman_worker.py:301-308`), and so is the
recreate branch (`module_utils/kolla_docker_worker.py:364-372`, `module_utils/kolla_podman_worker.py:618-623`). The
stop goes through the container's systemd unit `kolla-<name>-container.service`, whose `ExecStop` is
`/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:20-40, :72-75`). With
Docker the unit is used when it exists, `docker stop` with the same timeout otherwise
(`module_utils/kolla_docker_worker.py:426-442`); with Podman the worker writes the unit if needed and always stops
through it, except for one-shot containers (`module_utils/kolla_podman_worker.py:677-695`). `graceful_timeout` comes
from `docker_graceful_timeout: 60` (`group_vars/all.yml:148, :160`).

**Changed in 2025.1:** the unit template adds `PartOf=kolla.target`, and `compare_container` compares the whole unit
file (`module_utils/kolla_systemd_worker.py:20-40, :155-168`). A container recreated from a new image gets the new
unit when it is created (`module_utils/kolla_docker_worker.py:342-350`), and a restart rewrites it (`:450-470`); a
container that no 2025.1 run has created, recreated or restarted yet is reported as changed at its first 2025.1 check
if its unit was written by 2024.1 code ([F16](../reference/findings.md#f16)). With Docker on hosts outside the Red Hat
family, the new default `nofile` ulimit has the same effect on most containers created by 2024.1
([Predict and inspect a run §2](predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241)).

| Case | Who downloads | What restarts | Source |
|---|---|---|---|
| Same tag, rebuilt image, `deploy` without `pull` | nobody (image already present) | nothing | the local tag still resolves to the image the container runs (`module_utils/kolla_docker_worker.py:71-79, :107-122`; Podman `module_utils/kolla_podman_worker.py:263-276, :360-378`) |
| `-t nova pull` | every host in the nova plays, for nova images only; the common images (fluentd, kolla-toolbox, cron) are not pulled, because `common` is a separate play tagged `common` and no role declares it as a dependency (no `roles/*/meta` in 2025.1) | nothing | `site.yml:88-103`, `nova.yml:103-122, :125-147`, `roles/nova/tasks/pull.yml:1-3`, `roles/nova-cell/tasks/pull.yml:1-3`; `roles/service-images-pull/tasks/main.yml:2-18` (no `notify`) |
| `-t nova deploy` after that pull (only the nova-compute image rebuilt) | – | nova_compute **recreated** on every compute; **changed in 2025.1:** nova_libvirt and nova_ssh are not restarted | recreate if the container differs, else restart (`module_utils/kolla_docker_worker.py:352-374`); the shared check step notifies `Restart <item> container` for the changed items only (`roles/nova-cell/tasks/check-containers.yml:2-3`, `roles/service-check-containers/tasks/main.yml:4-41`) |
| New `openstack_tag`, `pull` | every host: 10 images per compute, 22 per controller, 12 per network node for this service set, counted as the enabled services mapped to each host | nothing | `roles/service-images-pull/tasks/main.yml:14`, `kolla_ansible/filters.py:22-109`; the hosts are mapped by the groups in `inventory/multinode` and the `<role>_services` defaults; [Compute scaling §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files) (per compute) |
| New `openstack_tag`, `deploy` | the rabbitmq image (version check) and the `nova_libvirt` image (libvirt checks on the first compute) are pulled lazily if `pull` was not run; the others in the handlers | **every container on every host recreated**: fluentd, cron, kolla_toolbox, iscsid, all nova, OVS db + vswitchd, neutron agents, haproxy, keepalived, proxysql, MariaDB (33 % batches), RabbitMQ (33 % batches)… | `openstack_tag` is built from `openstack_release` (`group_vars/all.yml:795-798`) and every `<svc>_tag` defaults to it (e.g. `roles/nova/defaults/main.yml:125`); `module_utils/kolla_docker_worker.py:107-122`; `roles/mariadb/handlers/main.yml:59-65` + `mariadb.yml:18-35`, `roles/rabbitmq/handlers/main.yml:2-5` + `rabbitmq.yml:30-49`; `roles/rabbitmq/tasks/version-check.yml:19-37` |

Image counts per host [CODE] (defaults of `group_vars/all.yml:831-958`, groups of `inventory/multinode`):

- compute (10): fluentd, kolla_toolbox, cron; iscsid (Cinder/LVM); nova_libvirt, nova_ssh, nova_compute;
  openvswitch_db, openvswitch_vswitchd; neutron_openvswitch_agent;
- network node (12): fluentd, kolla_toolbox, cron; haproxy, keepalived and, **changed in 2025.1**, proxysql
  (`enable_proxysql: "yes"`, `group_vars/all.yml:958`; group `loadbalancer`, `roles/loadbalancer/defaults/main.yml:12-15`;
  `haproxy_ssh` only with `enable_letsencrypt`, off by default, `group_vars/all.yml:913`); openvswitch_db,
  openvswitch_vswitchd; neutron_openvswitch_agent, neutron_dhcp_agent, neutron_l3_agent, neutron_metadata_agent;
- controller (22 images, 23 containers): fluentd, kolla_toolbox, cron; mariadb (**changed in 2025.1:** no
  `mariadb_clustercheck`, whose default follows `mariadb_loadbalancer`, now `proxysql`,
  `roles/mariadb/defaults/main.yml:42-45, :132`, `group_vars/all.yml:554`); rabbitmq; memcached; keystone,
  keystone_ssh, keystone_fernet; glance_api; placement_api; nova_api (also the image of the **new** `nova_metadata`
  container, `roles/nova/defaults/main.yml:33-38`), nova_scheduler, nova_conductor, nova_novncproxy
  (`nova_super_conductor` off: `enable_cells: "no"`, `group_vars/all.yml:859`); neutron_server; cinder_api,
  cinder_scheduler; heat_api, heat_api_cfn, heat_engine; horizon.

## 3. Which nodes download

Every host that runs at least one container whose image reference changed:

- **computes:** nova-compute, nova-libvirt, nova-ssh, OVS db/vswitchd, the neutron OVS agent, plus common and
  iscsid;
- **network nodes:** agents, OVS, haproxy, keepalived, proxysql;
- **controllers:** everything else.

`pull` itself never restarts anything. It is safe to run in advance; the 2025.1 docs ask for `kolla-ansible pull`
before `upgrade` (kolla-ansible `doc/source/user/operating-kolla.rst:163-167`).

## 4. Risks

- **Changing the tag and running `deploy`** (instead of `upgrade`) recreates the whole fleet in one go, without the
  upgrade-specific ordering (one-shot containers per image: [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)):
  - no `nova-status upgrade check` (the `nova_upgrade_checks` container runs in `roles/nova/tasks/upgrade.yml:5-35`
    only);
  - no RPC-pin reload plays (`nova.yml:180-256`, each with `kolla_action == 'upgrade'`);
  - no online data migrations (`nova.yml:258-302`, same condition), except Placement's: its bootstrap container
    (`KOLLA_BOOTSTRAP`, `roles/placement/tasks/bootstrap_service.yml:10-11`) runs `placement-manage db
    online_data_migrations` on every deploy (kolla `docker/placement/placement-api/extend_start.sh:5-9`). Ironic's
    does the same only with `ironic_enable_rolling_upgrade: no` (default `yes`, `roles/ironic/defaults/main.yml:316`;
    `roles/ironic/tasks/bootstrap_service.yml:5-16`, kolla `docker/ironic/ironic-api/extend_start.sh:5-9`);
  - RabbitMQ: both `deploy` and `upgrade` restart it in batches of 33 %, each node put in maintenance mode first when
    the cluster has more than one node (`roles/rabbitmq/handlers/main.yml:2-5`, `rabbitmq.yml:30-49`,
    `roles/rabbitmq/tasks/restart_services.yml:10-27`), and both run the version check, which refuses a jump of more
    than one minor version and a downgrade (`roles/rabbitmq/tasks/deploy.yml:2`, `roles/rabbitmq/tasks/upgrade.yml:2`,
    `roles/rabbitmq/tasks/version-check.yml:46-75`). The differences: `upgrade` also enables all stable feature flags
    on the running nodes (`roles/rabbitmq/tasks/upgrade.yml:8`, `roles/rabbitmq/tasks/feature-flags.yml:2-5`), and
    `deploy` runs `bootstrap.yml` (`roles/rabbitmq/tasks/deploy.yml:10`). Neither has a cluster-wide stop. The queue
    type checks are in the rabbitmq precheck ([F17](../reference/findings.md#f17));
  - Neutron (default `neutron_enable_rolling_upgrade: yes`, `roles/neutron/defaults/main.yml:707`): instead of
    expand → restart → contract (`roles/neutron/tasks/rolling_upgrade.yml:13-89`), `bootstrap_neutron` runs
    `neutron-db-manage … upgrade head` for neutron and for each enabled subproject with the new image **before** the
    handlers restart the old `neutron_server` containers (kolla `docker/neutron/neutron-server/extend_start.sh:5-13`;
    `roles/neutron/tasks/deploy.yml:20-23`, `roles/neutron/tasks/bootstrap_service.yml:2-21`,
    `roles/neutron/defaults/main.yml:702`) [CODE]. `neutron_subprojects` lists neutron-fwaas, networking-sfc,
    neutron-dynamic-routing, neutron-vpnaas, vmware-nsx and tap-as-a-service (`roles/neutron/defaults/main.yml:651-663`);
    none is enabled in the assumed deployment. [NOT AVAILABLE] Whether `upgrade head` then applies contract migrations
    under live old-version servers, and what that does to them.
- **An OVS image change** recreates `openvswitch_vswitchd` on every OVS host simultaneously under `upgrade` (always
  `kolla_serial=0` in 2025.1; play `site.yml:605-618`). [NOT AVAILABLE] Whether VM networking is interrupted on every
  compute at the same time. Upgrade OVS per batch of hosts with `--limit`:

  ```bash
  kolla-ansible upgrade -i multinode -t openvswitch --limit '<batch>'
  ```

  or, for a same-release image change, `kolla-ansible deploy -t openvswitch -e kolla_serial=<n>`.
- **Upgrade without a prior pull:** hosts download lazily inside the handler phase (`recreate_or_restart_container`
  pulls *before* stopping: Docker `module_utils/kolla_docker_worker.py:364-370`, Podman
  `module_utils/kolla_podman_worker.py:618-621`), which lengthens and staggers the restart window. The rabbitmq and
  `nova_libvirt` images are pulled earlier, by the version checks ([§1.1](#11-images)).
- **Podman back end:** the code paths above are read in `module_utils/kolla_podman_worker.py`; how they behave on a real
  Podman host is [NOT AVAILABLE] (source only, nothing was run).

## 5. Verification

- Before:
  - `docker images | grep <tag>` (or `podman images`) on a sample of hosts after `pull`;
  - the image IDs match the registry.
- After:
  - `docker ps --format '{{.Names}} {{.Image}}'` (or `podman ps`) shows the new tag everywhere;
  - `docker inspect -f '{{.Image}}' nova_compute` equals the pulled image ID.

## Related

- [Risk register](../risk/risk-register.md) — the risk items for these operations: [R11](../risk/risk-register.md#r11)
  (`kolla-ansible pull`), [R12](../risk/risk-register.md#r12) (changing `openstack_tag` and running `deploy` instead of
  `upgrade`), [R13](../risk/risk-register.md#r13) (rebuilt image pushed under the same tag),
  [R17](../risk/risk-register.md#r17) (`prune-images`) and [R7](../risk/risk-register.md#r7) (`openvswitch_vswitchd`
  restart or recreate)
- [Technical findings](../reference/findings.md) — [F4](../reference/findings.md#f4) (same-tag rebuilds are not picked
  up), [F16](../reference/findings.md#f16) (the first 2025.1 check of a container whose unit 2024.1 wrote) and
  [F19](../reference/findings.md#f19) (`upgrade` and `reconfigure` cannot be batched)
- [Open vSwitch](../components/openvswitch.md) — service card and where to look for the OVS image change of §4
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run, including "Pull
  first"
- [Write config first, apply in controlled batches](controlled-batches.md) — which commands and plays can be batched
  in 2025.1
- [Stop and destroy](stop-and-destroy.md) — `destroy --include-images`, which removes every Kolla image of the hosts
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — one-shot
  containers per image: what the environment variables run
- [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container) — how
  `kolla_container` decides to pull an image and to recreate a container, with Docker and with Podman
- [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code) — why only the changed container restarts in 2025.1
- [2024.1 update container images](../../2024.1/operations/update-container-images/) — the same page for 2024.1

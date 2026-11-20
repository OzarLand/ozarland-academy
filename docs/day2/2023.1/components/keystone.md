---
title: Keystone
description: Where the study covers Keystone (role keystone), from the single-service reconfigure and its restart risk to Fernet key handling, known bugs and open points.
tags: [keystone, reconfigure, serial, one-shot, risk, dependencies, bugs, unknowns]
---

# Keystone

This page is the starting point for Keystone, the `keystone` role: the containers `keystone`, `keystone_ssh` and
`keystone_fernet`, on the control nodes of the example inventory (`inventory/multinode:111-112`), selected by the tag
`keystone` (`site.yml:450-458`). Keystone is a hard deploy-time dependency of the 37 roles whose tasks use
`service-ks-register` (keystone itself included; grep of `roles/*/tasks`): registration runs `run_once`
(`roles/service-ks-register/tasks/main.yml:136`) with `openstack_interface` (`internal`) and authenticates against
`keystone_internal_url`; 2023.1 has no separate admin endpoint, `keystone_admin_url` is `keystone_internal_url`
(`roles/service-ks-register/defaults/main.yml:5`, `group_vars/all.yml:609,864-865,895-896`) [CODE] ([Component
dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses)). The
lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check
around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Reconfigure a single service
  §1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)

### Impact and risk

- **What the tag executes (`keystone`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Risks:** [R19](../risk/risk-register.md#r19), [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet B
  §3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#3-keystone-ansibleroleskeystone)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `keystone`), [Kolla
  images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start), [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [R19](../risk/risk-register.md#r19), precautions for a Keystone `reconfigure`: `ANSIBLE_SERIAL`; verify fernet key
  consistency before and after.
- [fact sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities),
  item 1: with the default serial 0, a reconfigure with a config change restarts `keystone_ssh`, then `keystone_fernet`,
  then `keystone`, each on all keystone hosts simultaneously. Set `ANSIBLE_SERIAL` for a rolling reconfigure.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2023.1 the stop goes through the container's systemd
  unit with `docker stop -t` `docker_graceful_timeout` (60 s, `group_vars/all.yml:140`), no longer 10 s. Precautions:
  drain long operations before restarts; raise `docker_graceful_timeout` if needed.
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering (the keystone group is one of the groups
  it names): treat inventory order as configuration; never reorder casually.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
  answers through the VIP, the container start times show which hosts restarted, and `docker ps --filter name=haproxy`
  shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `keystone`: fernet cron generator
  hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer. Status: all
  three unchanged in 2023.1 [CODE]: the generator computes `hour = time % HOUR_SPAN`
  (`roles/keystone/files/fernet_rotate_cron_generator.py:69`, the file is identical to Ussuri apart from a Python 2
  import); the precheck asserts `fernet_token_expiry <= 604800` (`roles/keystone/tasks/precheck.yml:43-53`) while the
  generator is fed `fernet_key_rotation_interval` (`roles/keystone/tasks/config.yml:195-200`); `fernet-push.sh` runs
  under `set -o errexit` and rsyncs to each peer in turn (`roles/keystone/templates/fernet-push.sh.j2:3,17-22`).
- [Q11](../troubleshooting/open-questions.md#q11): "Fernet key distribution failure modes". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "Keystone": the sources do not establish whether authentication, and so the other services' API requests, fails while
  keystone restarts or is down ([R19](../risk/risk-register.md#r19)); Fernet key distribution failure modes
  ([Q11](../troubleshooting/open-questions.md#q11)); whether Keystone still reads a removed policy file after the
  restart; the upstream semantics of `keystone-manage bootstrap`; whether the `keystone_fernet` container restarts when
  key 0 is missing.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether the SSH clients accept the new `nova_ssh` and `keystone_ssh` host keys after a
  recreate without failing.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [fact sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", ten items: reconfigure with a config change; what restarts
  keystone indirectly; Fernet push has no partial-failure handling; bug in the cron generator hour calculation; the
  precheck validates the wrong variable; under-rotation by design; shared SSH key; domain config cleanup; upgrade;
  reconfigure re-asserts identity state.
- [fact sheet B §3.10][sheet-b-310]: NOT AVAILABLE: whether the API services whose `[keystone_authtoken]` sections point
  keystonemiddleware at Keystone fail to authenticate requests while Keystone or memcached is unavailable.
- [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), row `keystone-fernet`: without key 0 on
  the node the start waits up to 10 × 60 s and the script exits 1 before the cron command is exec'd, so no rotation cron
  runs there meanwhile [CODE]; whether the container then restarts is [NOT AVAILABLE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 18: SSH host keys of `nova_ssh` and
  `keystone_ssh` change on every recreate, because `/etc/ssh` is on no volume [CODE]; whether the SSH client then
  accepts the new keys without failing is [NOT AVAILABLE: OpenSSH semantics].
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: the upstream semantics of `keystone-manage bootstrap`, in particular whether it resets the admin password to
  `keystone_admin_password`.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py keystone -->

| Item | Value |
|---|---|
| Play | site.yml:450 |
| Tags | keystone |
| Play host patterns | keystone |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `keystone`, `keystone_ssh`, `keystone_fernet` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap → flush handlers → distribute_fernet → register → register_identity_providers (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config-federation-oidc.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, distribute_fernet.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, register_identity_providers.yml, stop.yml, upgrade.yml |
| Templates | `crontab.j2`, `fernet-healthcheck.sh.j2`, `fernet-node-sync.sh.j2`, `fernet-push.sh.j2`, `fernet-rotate.sh.j2`, `keystone-fernet.json.j2`, `keystone-ssh.json.j2`, `keystone-startup.sh.j2`, `keystone.conf.j2`, `keystone.json.j2`, `ssh_config.j2`, `sshd_config.j2`, `wsgi-keystone.conf.j2` |
| Handlers (definition order) | Init keystone database upgrade; Restart keystone-ssh container; Restart keystone-fernet container; Restart keystone container; Finish keystone database upgrade |
| Key variables | `enable_keystone`, `keystone_token_provider`, `fernet_token_expiry`, `fernet_key_rotation_interval` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — `-t keystone reconfigure`, the command
  example of the page: scope, restarts and one-shot
- [HAProxy + Keepalived](haproxy-keepalived.md) — the loadbalancer play renders the keystone frontend under
  `-t keystone` (`site.yml:198-201`), and HAProxy restarts if it changed
- [Memcached](memcached.md) — Keystone's token cache
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — Keystone in
  the shared substrate that every OpenStack service uses
- [fact sheet B §3.10][sheet-b-310] — the runtime dependency of other services on Keystone, counted by role
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages

[sheet-b-310]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates

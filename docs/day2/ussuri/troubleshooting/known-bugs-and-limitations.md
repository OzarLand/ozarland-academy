---
title: Known bugs and limitations
description: The implementation limitations and bugs found in Kolla-Ansible ussuri-eol, by area, each with its evidence and its status.
tags: [bugs, evidence, serial, docker, kolla-set-configs, tags, upgrade, pull, bootstrap-servers, haproxy, keepalived, openvswitch, neutron, rabbitmq, mariadb, keystone, glance, cinder, heat, swift, octavia]
remember:
  - "<code>-e kolla_serial=N</code> is overridden by <code>ANSIBLE_SERIAL</code> (default 0) for <code>reconfigure</code>/<code>upgrade</code>; it is not passed for <code>deploy</code>. <span class=\"ev ev-code\">CODE</span>"
  - "<code>kolla_set_configs --check</code> compares only <code>config_files</code> entries: changes confined to <code>config.json</code> are not applied until the container restarts for another reason. <span class=\"ev ev-code\">CODE</span>"
  - "<code>graceful_timeout</code>/<code>client_timeout</code> from <code>docker_common_options</code> are ignored, and <code>restart_policy</code> is never compared. <span class=\"ev ev-code\">CODE</span>"
  - "A changed <code>heat_domain_admin_password</code> reaches <code>heat.conf</code> but never Keystone. <span class=\"ev ev-code\">CODE</span>"
  - "Certificates: test CA only, certs never renewed, new backend hosts not added. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "Does <code>kolla_docker</code> use <code>graceful_timeout</code> and <code>client_timeout</code> from <code>docker_common_options</code>?"
    options: ["Yes, both are applied to every container", "No: both are ignored"]
    answer: 1
    explain: "<code>graceful_timeout</code>/<code>client_timeout</code> from <code>docker_common_options</code> are ignored, and <code>restart_policy</code> is never compared <span class=\"ev ev-code\">CODE</span>."
  - q: "Why does the openvswitch task <code>Set system-id</code> report changed on every run?"
    options: ["It is a <code>command</code> task with no <code>changed_when</code>, and <code>command</code> always returns changed", "The system-id is regenerated on every run"]
    answer: 0
    explain: "<code>Set system-id</code> always reports changed: it is a <code>command</code> task with no <code>changed_when</code>, and <code>command</code> always returns changed <span class=\"ev ev-code\">CODE</span>."
  - q: "The <code>heat_domain_admin_password</code> is changed. Where does the new password end up?"
    options: ["In <code>heat.conf</code> and in Keystone", "In Keystone only", "In <code>heat.conf</code>, but never in Keystone"]
    answer: 2
    explain: "<code>bootstrap_heat</code> creates <code>heat_user_domain</code>/<code>heat_domain_admin</code> only when the domain is absent: a changed <code>heat_domain_admin_password</code> reaches <code>heat.conf</code> but never Keystone <span class=\"ev ev-code\">CODE</span>. Its impact is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
---

# Known bugs and limitations

The implementation limitations and bugs found in Kolla-Ansible `ussuri-eol`, by area, with the evidence and the status
of each row. Where a Status cell adds [NOT AVAILABLE], it names what the sources do not establish about the issue.

> [!NOTE]
> **Key answers**
>
> - **Implementation limitations and bugs of `ussuri-eol`, by area:** CLI, `site.yml`, `kolla_docker`, the kolla images
>   and individual roles (table below).

| Area | Issue | Evidence | Status |
|---|---|---|---|
| CLI | `-e kolla_serial=N` is overridden by `ANSIBLE_SERIAL` (default 0) for `reconfigure`/`upgrade`; it is not passed for `deploy` | `tools/kolla-ansible:236,430,439` | [CODE] |
| CLI | `--ask-vault-pass` overwrites `VERBOSITY` with a copy of `EXTRA_OPTS` | `tools/kolla-ansible:320-323` | [CODE] |
| CLI | `--include-dev:` declared with an argument but used as a flag; the command line is executed unquoted | `tools/kolla-ansible:116,216,284-287` | [CODE] [fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md) |
| site.yml | cyborg play uses `serial` instead of `kolla_serial` | `site.yml:1028` | [CODE] |
| site.yml | placement haproxy include lacks `when: enable_placement` | `site.yml:289-292` | [CODE] |
| kolla_docker | `graceful_timeout`/`client_timeout` from `docker_common_options` ignored ([F3](../reference/findings.md#f3)); `restart_policy` never compared (FIXME `:21`) | `kolla_docker.py:21,991,1011,1037-1047` | [CODE] |
| kolla images | `kolla_set_configs --check` compares only `config_files` entries ([F14](../reference/findings.md#f14)): changes confined to `config.json` (`command`, `permissions`; all of memcached's settings) are never detected, so neither `genconfig` + `deploy-containers` nor a later run applies them until the container restarts for another reason; a newly added optional file makes it exit 2 and fails `check-containers` unless an entry listed before it differs (then 1); `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run; a restart never removes files whose entry was dropped | kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578` | [CODE] |
| common | `-t common` no-op ([F2](../reference/findings.md#f2)) | `roles/common/tasks/main.yml:1-10`; [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) | [CODE] |
| haproxy | Restart instead of reload; stale `services.d` files never removed; keepalived priority from inventory order; upgrade "Stopping all slave keepalived" without an `enable_keepalived` guard and with raw interface names | [fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour) | [CODE]; effect of the upgrade bugs [NOT AVAILABLE] |
| openvswitch | `Set system-id` always reports changed | `roles/openvswitch/tasks/post-config.yml:3-5` (a `command` task with no `changed_when`; `command` always returns changed, ansible 2.9.27 `lib/ansible/modules/commands/command.py:334`) | [CODE] |
| neutron | `upgrade` with the default `neutron_enable_rolling_upgrade: "yes"` expands/contracts only `neutron`, `neutron-fwaas` and `neutron-vpnaas`: `neutron-dynamic-routing`, which the `KOLLA_BOOTSTRAP` container migrates on `deploy`, is never migrated by `upgrade`, and the image's rolling `neutron-db-manage` calls pass no `--config-file`. `has_offline_migrations` runs on the first neutron-server host with `ignore_errors`; any non-zero rc (a failed `docker exec` included) stops `neutron_server` on every neutron-server host in the play until the handler flush after the contract container | `roles/neutron/defaults/main.yml:411-412`; `roles/neutron/tasks/upgrade.yml:2-3`; `roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67,69-93`; `roles/neutron/tasks/bootstrap_service.yml:21-22`; kolla `docker/neutron/neutron-server/extend_start.sh:5-12,34-38` | [CODE]; impact on the Neutron API [NOT AVAILABLE] |
| ovs-dpdk | `pull` looks up a non-existent `ovs_services` variable; the NIC mapping file is written once; the 300 s wait handler has no port | [fact sheet A §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role) | [CODE] |
| rabbitmq | outward RabbitMQ `pull` looks up `outward_rabbitmq_services` | [fact sheet B §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities) (item 6); `site.yml:563` (`project_name: outward_rabbitmq`), `roles/rabbitmq/tasks/pull.yml:2-3`, `roles/service-images-pull/tasks/main.yml:14`; ansible 2.9.27 `lib/ansible/plugins/lookup/vars.py:80-94` | [CODE]: with outward RabbitMQ enabled, that variable is not defined anywhere, the `vars` lookup raises an undefined-variable error and "Pull images" fails on the outward-rabbitmq hosts |
| rabbitmq | the image writes `.erlang.cookie` only in the bootstrap container (new volume); a cookie change recreates the brokers (env compare) but they keep the old cookie, while `kolla_toolbox` gets the new one | kolla `docker/rabbitmq/extend_start.sh:7-18`; `roles/rabbitmq/tasks/bootstrap.yml:26`; `roles/common/tasks/config.yml:242-250` | [CODE]; consequences [NOT AVAILABLE] |
| mariadb | the restart waves have no `any_errors_fatal`; recovery stops healthy nodes; clustercheck started even when disabled | [fact sheet B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order), [§1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) (items 5–6); `roles/mariadb/handlers/main.yml:66-78`; ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:548-561,1019-1020,1045-1063` | [CODE]: a node that fails its WSREP wait marks only its own host failed, and the next wave still restarts its nodes ([R9](../risk/risk-register.md#r9)); whether the failed node is then still joining, and how large the quorum and availability risk is, [NOT AVAILABLE] |
| keystone | fernet cron generator hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer | [fact sheet B §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities) (items 3–5); `roles/keystone/files/fernet_rotate_cron_generator.py:61-64,70-72`, `roles/keystone/templates/fernet-push.sh.j2:3-10` | [CODE] |
| glance | global `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches silently when Swift/Ceph is enabled | [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance) | [CODE] |
| cinder | no `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a Ceph config | [fact sheet C §3](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#3-cinder) | [CODE] |
| heat | `bootstrap_heat` creates `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches `heat.conf` but never Keystone | kolla `docker/heat/heat-api/extend_start.sh:8-14`; `roles/heat/templates/heat.conf.j2:12-13` | [CODE]; impact [NOT AVAILABLE] |
| swift | no handlers are notified (deploy does not apply config/ring changes); `stop.yml` wrong container name; precheck probes rsync port 873 vs 10873 | [fact sheet D](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md) | [CODE]; runtime effects [NOT AVAILABLE] |
| octavia | upgrade removes the octavia admin role on `admin` without re-registering; no amphora resources are created | [fact sheet D](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md) | [CODE] |
| masakari | instancemonitor uses `qemu+tcp` without SASL while nova-libvirt enables SASL | [fact sheet D](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md); `roles/masakari/templates/masakari-monitors.conf.j2:17`, `roles/nova-cell/defaults/main.yml:431`, `roles/nova-cell/templates/libvirtd.conf.j2:12` | [CODE]; effect on the instancemonitor [NOT AVAILABLE] |
| baremetal | Docker restarted on `daemon.json` change on all hosts at once; `docker_custom_option` changes are never applied; Docker masked during re-runs on Debian/Ubuntu; `/etc/hosts` lists every baremetal host (O(N²) templating, stale with `--limit`) | [fact sheet E §1–5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#1-ansiblekolla-hostyml-the-bootstrap-servers-command) | [CODE]; runtime effects [NOT AVAILABLE] |
| certificates | test CA only; certs never renewed; new backend hosts not added | [fact sheet A §8](../reference/factsheets/a-infra-lb-ovn.md#8-certificatesyml-playbook--certificates-role), [E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md) | [CODE] |

## Related

- [Troubleshooting](index.md) — the symptom index, which points to these rows by what an operator sees
- [Findings](../reference/findings.md) — the headline findings; the rows `kolla_docker`, `kolla images` and `common`
  cite [F3](../reference/findings.md#f3), [F14](../reference/findings.md#f14) and [F2](../reference/findings.md#f2)
- [Per-role fact sheets](../reference/factsheets/index.md) — the fact sheets that the role rows cite as evidence, and
  their corrections
- [Fact sheet D
  §7](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#7-consolidated-bugs-and-oddities) — the
  consolidated bugs and oddities of the roles of fact sheet D
- [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) — what
  `kolla_set_configs --check` compares and what it never compares (row `kolla images`)
- [What is not known](what-is-not-known.md) — the effects that the Status column marks [NOT AVAILABLE], by topic
- [Open questions](open-questions.md) — the open questions Q1 to Q14

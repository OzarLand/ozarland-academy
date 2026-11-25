---
title: Why a small change creates a large workload
description: Seven small changes that become a large workload in Kolla-Ansible 2025.1, each with the reason and the source.
tags: [risk, scaling, nova, neutron, rabbitmq, images, reconfigure, systemd, serial]
remember:
  - "One option for nova-compute in <code>nova/nova-compute.conf</code> is not small: it targets every compute, all at once. Changed in 2025.1: only <code>nova_compute</code> restarts, since loop-notify is gone; <code>nova/&lt;host&gt;/nova-compute.conf</code> reaches that compute only. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: a rebuilt image of one service, once pulled, restarts the containers of that image only, no longer their siblings. <span class=\"ev ev-code\">CODE</span>"
  - "One extra controller changes the transport URL in every messaging service everywhere."
  - "One container-engine option such as <code>docker_graceful_timeout</code> changes the systemd unit of every container, and the next check of each container reports it as changed. <span class=\"ev ev-code\">CODE</span>"
  - "Every run pays the per-host work: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute, independently of restarts. <span class=\"ev ev-code\">CODE</span>"
scenarios:
  - title: "A one-line nova-compute change"
    situation: "Your cloud has 40 computes. A ticket asks you to change one option for nova-compute on all of them. Your colleague says: \"It's a one-line change in <code>nova/nova-compute.conf</code>, just run <code>reconfigure -e kolla_serial=5</code> now and close the ticket.\""
    ask: "What would you do?"
    choices:
      - text: "Write the config first with <code>genconfig</code>, then apply it with <code>deploy-containers --limit</code>, batch by batch."
        verdict: "best"
        why: "One option for nova-compute targets every compute <span class=\"ev ev-code\">CODE</span>, and <code>nova_compute</code> restarts on each of them. The page points to the pattern \"Write config first, apply in controlled batches\": <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
      - text: "Run the <code>reconfigure -e kolla_serial=5</code> as suggested."
        verdict: "avoid"
        why: "In 2025.1 <code>reconfigure</code> adds its own <code>kolla_serial=0</code> after yours <span class=\"ev ev-code\">CODE</span>, so all 40 computes restart <code>nova_compute</code> in one batch (R32). <code>deploy -e kolla_serial=5</code> would batch the same tasks."
      - text: "Run <code>reconfigure</code> on all computes in one go, but only at night."
        verdict: "risky"
        why: "The time of day does not change the size of the change: it still targets every compute at once. The page's pattern applies the config in controlled batches with <code>deploy-containers --limit</code>."
  - title: "Raise the stop timeout"
    situation: "A colleague wants heat-engine to get more time to stop cleanly, and proposes to raise <code>docker_graceful_timeout</code> from 60 to 300 in <code>globals.yml</code> and run <code>reconfigure -t heat</code>, \"since only Heat is concerned\"."
    ask: "What would you know before you agree?"
    choices:
      - text: "That the value is part of the systemd unit of every container, so the next check of each container the run reaches reports a change and restarts it; plan it as a fleet-wide restart, in batches."
        verdict: "best"
        why: "<code>docker_graceful_timeout</code> goes into <code>docker_common_options</code>, which every container task passes, and into the unit text; <code>compare_container</code> compares the whole unit file <span class=\"ev ev-code\">CODE</span>. <code>-t heat</code> reaches only the Heat containers, but every later run that checks another container restarts it."
      - text: "Nothing: a stop timeout only matters when a container stops, so the change restarts nothing."
        verdict: "avoid"
        why: "The unit text changes, and <code>compare_container</code> reports a container as changed when its unit file differs from the rendered one <span class=\"ev ev-code\">CODE</span>; the restart handler then restarts it."
      - text: "That only Heat will ever see the new value, because the run is tagged <code>heat</code>."
        verdict: "risky"
        why: "The tag limits which containers this run checks, not which containers the global value reaches: the next untagged or other-tag run checks the other containers against the new unit text and restarts them <span class=\"ev ev-code\">CODE</span>."
quiz:
  - q: "You change one option for nova-compute in <code>/etc/kolla/config/nova/nova-compute.conf</code>. Why is it a large change?"
    options: ["It is not: one container on one host restarts", "It targets every compute, and <code>nova_compute</code> restarts on all of them at once"]
    answer: 1
    explain: "First row of the table. In 2025.1 the restart is <code>nova_compute</code> only, but on every compute."
  - q: "In 2025.1, the image of one service is rebuilt and pulled. What else restarts?"
    options: ["Nothing else: only the containers of that image", "Every other container of its role on the same host"]
    answer: 0
    explain: "Row \"Rebuilt image of one service\": the shared check notifies only the containers whose comparison changed."
  - q: "You change <code>docker_graceful_timeout</code>. Which containers can a later run restart?"
    options: ["None: the timeout is read only when a container stops", "Every long-running container it checks, because their systemd unit text changed"]
    answer: 1
    explain: "Row \"One container-engine option\" <span class=\"ev ev-code\">CODE</span>."
  - q: "Does a run with no change cost anything per compute?"
    options: ["No, nothing happens", "Yes: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute"]
    answer: 1
    explain: "Every run pays the per-host work <span class=\"ev ev-code\">CODE</span>, independently of restarts."
---

# Why a small change creates a large workload

Why a small change can create a large workload in Kolla-Ansible 2025.1: seven small changes, each with why it is large
and the source lines and sections that show it. The seven rows of 2024.1 still hold, two of them smaller because
loop-notify is gone ([Tags §2.4](tags.md#24-loop-notify-is-gone-in-20251-code)). The per-host work that every run pays,
independently of restarts, closes the page.

<img src="../assets/images/S3-small-change-large-effect.webp" width="1536" height="1024" loading="lazy" alt="Jo, holding a crate, and LUMO, reading, stand by a large brass gear mechanism on a bench where a small brass key lies on a parchment.">

| Small change | Why it is large | Source |
|---|---|---|
| One option for nova-compute | `/etc/kolla/config/nova/nova-compute.conf` targets every compute, all at once with the default serial 0 (and `reconfigure` cannot be batched, [R32](risk-register.md#r32)). **Changed in 2025.1:** only `nova_compute` restarts; `nova_libvirt` and `nova_ssh` keep running, since their files did not change. The same option in `/etc/kolla/config/nova/<host>/nova-compute.conf` is merged into that host's `nova-compute/nova.conf` only, so it reaches one compute | `nova.yml:125-147`; `roles/nova-cell/tasks/config.yml:120-136` (sources at `:129`, `:131`); `roles/nova-cell/tasks/check-containers.yml:2-3`; `roles/service-check-containers/tasks/main.yml:34-41`; [Tags §2.4](tags.md#24-loop-notify-is-gone-in-20251-code); [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| `enable_<new service>: yes` | changes fluentd/logrotate on every host (at the next run of the `common` play: no tag or `-t common`) and `nova.conf` sections on every compute (e.g. `[barbican]`) | `roles/common/defaults/main.yml:146-150`, `roles/common/tasks/config.yml:171-181`; `site.yml:88-103`; `roles/nova-cell/templates/nova.conf.j2:249-254`; [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| One extra controller | changes the transport URL in every messaging service everywhere | `group_vars/all.yml:274`, `:284`; [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |
| A server-side ML2 option | still does not reach the agents: `ml2_conf.ini` (and its overrides) is rendered for `neutron-server` and `neutron-infoblox-ipam-agent` only, and `openvswitch_agent.ini` does not merge the `ml2_conf.ini` overrides. A file added under `neutron/plugins/` in the custom config is still copied to every Open vSwitch agent (and to `neutron-server`) and restarts them; the Linux bridge agent is gone in 2025.1 | `roles/neutron/tasks/config.yml:134-150`, `:152-164`, `:12-18`, `:377-396`; [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code) |
| Rebuilt image of one service | once the new image is on the host (a same-tag rebuild needs an explicit `pull`), the containers of that image are recreated on every host that runs them. **Changed in 2025.1:** their siblings on the same host no longer restart, since the shared check notifies only the containers whose comparison changed | `module_utils/kolla_docker_worker.py:107-122` (Podman: `module_utils/kolla_podman_worker.py:360-378`); `roles/service-check-containers/tasks/main.yml:4-41`; [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [F4](../reference/findings.md#f4) |
| Any OpenStack API service `-t <svc>` | runs the service's include in the `loadbalancer` play (haproxy configuration, and the service's block of `external-frontend-map` when `haproxy_single_external_frontend` is set, default `false`) and Keystone registration even with no change. **Changed in 2025.1:** the new frontend is written but HAProxy is not restarted until a run with `-t haproxy` or no tag ([F18](../reference/findings.md#f18)). It does not run common, since no role has a `meta` directory and the common play is tagged `common` only; the DB sync runs on every `deploy` and, for most services, on every reconfigure. Neutron too: its bootstrap (`neutron-db-manage ... upgrade head`) has no `kolla_action` condition and runs on every `deploy` and `reconfigure`. Infrastructure tags such as `-t haproxy` run the `loadbalancer` play, whose 38 service includes are all evaluated and run for the enabled services, but no Keystone registration or DB sync | [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), [Reconfigure a single service §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects); `site.yml:88-103`, `:105-328` (final check at `:319-324`); `roles/haproxy-config/tasks/main.yml:23-50`, `group_vars/all.yml:1067`; `roles/neutron/tasks/reconfigure.yml:2`, `roles/neutron/tasks/deploy.yml:13-23`, `roles/neutron/tasks/bootstrap_service.yml:2-21`; kolla `docker/neutron/neutron-server/extend_start.sh:5-13` |
| One container-engine option (`docker_graceful_timeout`, `docker_client_timeout`, `docker_restart_policy`, `docker_restart_policy_retry`) | the value goes into `docker_common_options`, which every container task passes, and into the systemd unit text of every container. `compare_container` compares the whole unit file with the rendered one, so the next check of every long-running container reports it as changed and its restart handler restarts it, rewriting the unit. One-shot containers have no unit. A `docker_restart_policy` change between `unless-stopped` and `always` renders the same `Restart=always` and changes nothing | `group_vars/all.yml:148`, `:151-162`; `library/kolla_container.py:357-389`; `module_utils/kolla_systemd_worker.py:20-40`, `:57-80`, `:155-168`, `:173-186`; `module_utils/kolla_container_worker.py:32`, `:58-65`; `module_utils/kolla_docker_worker.py:450-470`; [F16](../reference/findings.md#f16) |

> [!NOTE]
> The first 2025.1 `deploy` or `reconfigure` after an upgrade from 2024.1 is a large workload with no operator change
> at all [CODE]: the 2025.1 unit template adds `PartOf=kolla.target`, so every container whose unit 2024.1 wrote is
> reported as changed at its first 2025.1 check, and on Docker hosts outside the Red Hat family the new default `nofile`
> ulimits make most containers be recreated ([F16](../reference/findings.md#f16);
> `module_utils/kolla_systemd_worker.py:20-40`, `:155-168`; `group_vars/all.yml:201-224`); and every messaging service
> now renders the queue manager, transient quorum queues and stream fanout (`group_vars/all.yml:292`; e.g.
> `roles/nova-cell/templates/nova.conf.j2:201-206`; [F17](../reference/findings.md#f17)). The checks to make before
> that run are in [Predict and inspect a run
> §2](../operations/predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241).

And independently of restarts, **every run pays the per-host work** [CODE]. Still holds in 2025.1: every full `deploy`
or `reconfigure` makes 10 `compare_container` calls per compute (common 3, iscsid with Cinder LVM, openvswitch 2,
neutron 1, nova-cell 3), each one a `kolla_set_configs --check` exec in the container once it exists and no compared
parameter differs (`roles/common/tasks/check-containers.yml:2-3`, `roles/nova-cell/tasks/check-containers.yml:2-3`,
`roles/openvswitch/tasks/check-containers.yml:2-3`, `roles/neutron/tasks/check-containers.yml:2-3`,
`roles/iscsi/tasks/check-containers.yml:2-3`, all through `roles/service-check-containers/tasks/main.yml:4-29`;
`module_utils/kolla_container_worker.py:58-65`; `module_utils/kolla_docker_worker.py:146-181`, Podman
`module_utils/kolla_podman_worker.py:524-552`). The common three run only when the `common` play runs (no tag or
`-t common`, `site.yml:88-103`). The remote module invocations of a no-change `-t nova` run, 29 per compute in 2025.1
(27 in 2024.1), are counted from the task files in [Compute scaling
§2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files). The number of
task results per compute is [NOT AVAILABLE].

## Related

- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
- [Tags §2.4](tags.md#24-loop-notify-is-gone-in-20251-code) — the shared check that replaced loop-notify
- [Technical findings](../reference/findings.md) — [F6](../reference/findings.md#f6): global inputs are rendered into
  per-host files; [F16](../reference/findings.md#f16): the unit text is part of the container check
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Risk register](risk-register.md) — the risks, from [R1](risk-register.md#r1)
- [2024.1 small change, large workload](../../2024.1/risk/small-change-large-workload/) — the same page for 2024.1

---
title: Why a small change creates a large workload
description: Six small changes that become a large workload in Kolla-Ansible Ussuri, each with the reason and the source.
tags: [risk, scaling, loop-notify, nova, neutron, rabbitmq, images, reconfigure]
remember:
  - "One option for nova-compute is not small: it targets every compute, and loop-notify adds the libvirt and ssh restarts."
  - "A rebuilt image of one service restarts its sibling containers on the same host too."
  - "One extra controller changes the transport URL in every messaging service everywhere."
  - "Every run pays the per-host work: every full <code>deploy</code> or <code>reconfigure</code> makes 11 <code>compare_container</code> calls per compute, independently of restarts. <span class=\"ev ev-code\">CODE</span>"
  - "Write config first, apply in controlled batches: <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
scenarios:
  - title: "A one-line nova-compute change"
    situation: "Your cloud has 40 computes. A ticket asks you to change one option for nova-compute. Your colleague says: \"It's a one-line change, just run a full <code>reconfigure</code> now and close the ticket.\""
    ask: "What would you do?"
    choices:
      - text: "Write the config first with <code>genconfig</code>, then apply it with <code>deploy-containers --limit</code>, batch by batch."
        verdict: "best"
        why: "One option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts. The page points to the pattern \"Write config first, apply in controlled batches\": <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
      - text: "Run a full <code>reconfigure</code> of the cloud right away, as suggested."
        verdict: "avoid"
        why: "The change is not small: one option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts. On top of that, every run pays the per-host work <span class=\"ev ev-code\">CODE</span>: every full <code>deploy</code> or <code>reconfigure</code> makes 11 <code>compare_container</code> calls per compute."
      - text: "Run <code>reconfigure</code> on all computes in one go, but only at night."
        verdict: "risky"
        why: "The time of day does not change the size of the change: it still targets every compute, and loop-notify still adds the libvirt and ssh restarts on each of them. The page's pattern applies the config in controlled batches with <code>deploy-containers --limit</code>."
quiz:
  - q: "You change one option for nova-compute. Why is it a large change?"
    options: ["It is not: only one container restarts", "It targets every compute, and loop-notify adds the libvirt and ssh restarts"]
    answer: 1
    explain: "First row of the table."
  - q: "The image of one service is rebuilt. What else restarts?"
    options: ["Nothing else", "Its sibling containers on the same host"]
    answer: 1
    explain: "Row \"Rebuilt image of one service\"."
  - q: "Does a run with no change cost anything per compute?"
    options: ["No, nothing happens", "Yes: every full <code>deploy</code> or <code>reconfigure</code> makes 11 <code>compare_container</code> calls per compute"]
    answer: 1
    explain: "Every run pays the per-host work <span class=\"ev ev-code\">CODE</span>, independently of restarts."
---

# Why a small change creates a large workload

Why a small change can create a large workload: six small changes, each with why it is large and the source lines and
sections that show it. The per-host work that every run pays, independently of restarts, closes the page.

<img src="../assets/images/S3-small-change-large-effect.webp" width="1536" height="1024" loading="lazy" alt="Jo, holding a crate, and LUMO, reading, stand by a large brass gear mechanism on a bench where a small brass key lies on a parchment.">

| Small change | Why it is large | Source |
|---|---|---|
| One option for nova-compute | targets every compute; loop-notify adds libvirt + ssh restarts | `nova.yml:117-135`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| `enable_<new service>: yes` | changes fluentd/logrotate on every host and `nova.conf` sections on every compute | `roles/common/defaults/main.yml:105-109`, `roles/common/tasks/config.yml:163-173`; [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| One extra controller | changes the transport URL in every messaging service everywhere | `group_vars/all.yml:206`; [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |
| A server-side ML2 option | also merged into every OVS agent config | `roles/neutron/tasks/config.yml:172-190`; [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code) |
| Rebuilt image of one service | its siblings on the same host restart too | `library/kolla_docker.py:403-418`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code) |
| Any OpenStack API service `-t <svc>` | runs common, the service's haproxy include and Keystone registration even with no change; the DB sync runs on every `deploy` and, for most services, on every reconfigure (Neutron: `deploy` only by default). Infrastructure tags such as `-t haproxy` run no Keystone registration or DB sync | [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), [Reconfigure a single service §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects); `site.yml:126-392` |

And independently of restarts, **every run pays the per-host work** [CODE]. Per compute, a no-change `-t nova` run makes
46 remote module invocations (53 on compute001), and every full `deploy` or `reconfigure` makes 11 `compare_container`
calls, counted from the task files in [Compute scaling
§2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files). The number of task
results per compute is [NOT AVAILABLE].

## Related

- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
- [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify
- [Technical findings](../reference/findings.md) — [F6](../reference/findings.md#f6): global inputs are rendered into
  per-host files
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Risk register](risk-register.md) — the risks [R1–R25](risk-register.md#r1)

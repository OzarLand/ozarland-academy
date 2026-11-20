---
title: "Production guide"
description: "A visual memo for OpenStack operators: one operational lesson per page, to remember, apply and share."
---

# 🗺️ Production guide

**A visual memo for OpenStack operators: one operational lesson per page, to remember, apply and share.**

[Catalog](#catalog) · [How to read a memo](#-how-to-read-a-memo) · [Not covered yet](#-not-covered-yet) ·
[Build](#-build-it-yourself) · [Contribute](#-contributing)

<p align="center">
<a href="categories/compute/fence-before-evacuate.md"><img src="dist/pg-07-fence-before-evacuate.png" alt="Fence before you evacuate" width="270"></a>
<a href="categories/vm-lifecycle/vm-stuck-in-build.md"><img src="dist/pg-01-vm-stuck-in-build.png" alt="VM stuck in BUILD?" width="270"></a>
<a href="categories/control-plane/control-plane-down.md"><img src="dist/pg-15-control-plane-down.png" alt="Control plane down: what runs?" width="270"></a>
</p>

---

A field guide, not a manual. Each memo takes one situation an operator meets in production and answers four
questions in under a minute: what is happening, what to check first, what not to do yet, and what to remember.
The procedure itself, with every command and its limits, stays in
the [VM runbooks](../runbooks/): every memo links to the runbook it was
written from.

No imposed tools, no single way of operating OpenStack.

> **One memo = one operational lesson = one memorable visual.**

## 🧭 How to read a memo

Every memo has the same seven parts, in the same place:

| Part | What it tells you |
|---|---|
| **Title** | The situation, as a short question or statement |
| **Situation** | What you see, and what it means |
| **Diagram** | The mechanism: where a request stops, which case you are in, what differs between two things that look alike |
| **First checks** · green | Four things to look at. Always read-only: they never change the platform |
| **Think before acting** · amber, red | What not to do yet, and the risk of the usual fixes |
| **Operational lesson** | The one sentence to keep |
| **Go deeper** | The path of the runbook in the VM runbooks of OzarLand Academy, and how much that runbook was verified |

Colour means one thing only, the risk of an action, with the same vocabulary as the
[OzarLand risk warnings](https://github.com/OzarLand/ozarland/blob/main/docs/conventions/risk-warnings.md):

| | On a memo | Meaning |
|:-:|---|---|
| 🟩 | Green | Read-only, or the healthy case |
| 🟧 | Amber, **State-changing.** | Changes the platform in a bounded way |
| 🟥 | Red, **Destructive.** or **Avoid.** | Can lose data or end workloads, or a shortcut that makes things worse |
| ⬜ | Grey, **Know this.** | A fact that changes how you read the situation |

> [!WARNING]
> A memo is a memory aid, not a procedure. It is as reliable as the runbook behind it, and it says how reliable
> that is: the pill at the bottom right shows the runbook's status and release. Today the source runbooks are
> `lab-verified` or `draft` on OpenStack 2026.1, mostly with Kolla-Ansible and ML2/OVS, and none has been confirmed
> on a production platform by an operator other than its author. A `draft` runbook's commands were not run by anyone
> but its author. Each memo's page has a **Where this holds** paragraph:
> read it, then read the runbook, before any ⚠️ or 🛑 action.

## Catalog

<!-- count:start -->
**44 memos** across 6 categories.
<!-- count:end -->
Click a memo for its page: the image, the same content as text, the runbook links and the LinkedIn kit.

<!-- catalog:start -->
### VM lifecycle

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/vm-lifecycle/vm-stuck-in-build.md"><img src="dist/pg-01-vm-stuck-in-build.png" alt="VM stuck in BUILD?" width="150"></a> | **PG-01**<br>[VM stuck in BUILD?](categories/vm-lifecycle/vm-stuck-in-build.md) | A networking problem wearing a compute symptom. | [lifecycle/…](../runbooks/lifecycle/instance-stuck-in-build-waiting-for-vif-plugged/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/no-valid-host.md"><img src="dist/pg-02-no-valid-host.png" alt="No valid host, with free capacity?" width="150"></a> | **PG-02**<br>[No valid host, with free capacity?](categories/vm-lifecycle/no-valid-host.md) | Three places a build can stop before any compute. Read the exact message first. | [scheduling/…](../runbooks/scheduling/no-valid-host-with-free-capacity/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/max-retries-exceeded.md"><img src="dist/pg-03-max-retries-exceeded.png" alt="Exceeded maximum number of retries?" width="150"></a> | **PG-03**<br>[Exceeded maximum number of retries?](categories/vm-lifecycle/max-retries-exceeded.md) | The fault is a summary. The cause is in the log of each compute that tried. | [scheduling/…](../runbooks/scheduling/build-fails-exceeded-maximum-number-of-retries/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/vm-stuck-in-deleting.md"><img src="dist/pg-04-vm-stuck-in-deleting.png" alt="VM stuck in deleting?" width="150"></a> | **PG-04**<br>[VM stuck in deleting?](categories/vm-lifecycle/vm-stuck-in-deleting.md) | A delete has two paths. Know which one Nova will take before you retry. | [lifecycle/…](../runbooks/lifecycle/instance-stuck-in-deleting/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/active-but-frozen.md"><img src="dist/pg-05-active-but-frozen.png" alt="ACTIVE in Nova, frozen for users?" width="150"></a> | **PG-05**<br>[ACTIVE in Nova, frozen for users?](categories/vm-lifecycle/active-but-frozen.md) | Nova does not watch the disk. Monitor the instance store and the power state. | [lifecycle/…](../runbooks/lifecycle/compute-disk-full-instance-paused/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/shutoff-by-itself.md"><img src="dist/pg-21-shutoff-by-itself.png" alt="SHUTOFF by itself?" width="150"></a> | **PG-21**<br>[SHUTOFF by itself?](categories/vm-lifecycle/shutoff-by-itself.md) | The scheduler trusts the inventory. Make it match what the host really uses. | [lifecycle/…](../runbooks/lifecycle/instance-shut-off-by-host-oom-killer/)<br>`draft` |
| <a href="categories/vm-lifecycle/resize-not-finished.md"><img src="dist/pg-22-resize-not-finished.png" alt="Resize not finished?" width="150"></a> | **PG-22**<br>[Resize not finished?](categories/vm-lifecycle/resize-not-finished.md) | VERIFY_RESIZE is not stuck. It waits for a decision only the owner can make. | [lifecycle/…](../runbooks/lifecycle/resize-stuck-in-verify-resize-or-failed/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/snapshot-never-finishes.md"><img src="dist/pg-29-snapshot-never-finishes.png" alt="Snapshot never finishes?" width="150"></a> | **PG-29**<br>[Snapshot never finishes?](categories/vm-lifecycle/snapshot-never-finishes.md) | A slow snapshot is often just a large disk. No error in the compute log? Let it finish. | [lifecycle/…](../runbooks/lifecycle/snapshot-stuck-in-image-uploading/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/guest-broken-nova-says-active.md"><img src="dist/pg-30-guest-broken-nova-says-active.png" alt="Guest broken, Nova says ACTIVE?" width="150"></a> | **PG-30**<br>[Guest broken, Nova says ACTIVE?](categories/vm-lifecycle/guest-broken-nova-says-active.md) | The fault is in the guest, the data is intact. Rescue mode gets you to the disk. | [lifecycle/…](../runbooks/lifecycle/rescue-mode-repair-an-unbootable-guest/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/console-does-not-open.md"><img src="dist/pg-31-console-does-not-open.png" alt="Console does not open?" width="150"></a> | **PG-31**<br>[Console does not open?](categories/vm-lifecycle/console-does-not-open.md) | A console is a chain of hops. The API answer or the proxy log says which one refused. | [lifecycle/…](../runbooks/lifecycle/console-not-available-or-disconnects/)<br>`draft` |
| <a href="categories/vm-lifecycle/boot-from-volume-fails.md"><img src="dist/pg-32-boot-from-volume-fails.png" alt="Boot from volume fails?" width="150"></a> | **PG-32**<br>[Boot from volume fails?](categories/vm-lifecycle/boot-from-volume-fails.md) | The fault names the volume. Read its status and Cinder's message before you retry. | [scheduling/…](../runbooks/scheduling/instance-fails-to-boot-from-volume/)<br>`lab-verified` |
| <a href="categories/vm-lifecycle/image-too-big-for-the-flavor.md"><img src="dist/pg-33-image-too-big-for-the-flavor.png" alt="Image too big for the flavor?" width="150"></a> | **PG-33**<br>[Image too big for the flavor?](categories/vm-lifecycle/image-too-big-for-the-flavor.md) | The file size is not the disk size. Compare the flavor with the image's virtual size. | [scheduling/…](../runbooks/scheduling/image-larger-than-flavor-disk/)<br>`lab-verified` |

### Compute operations

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/compute/compute-down-is-not-host-down.md"><img src="dist/pg-06-compute-down-is-not-host-down.png" alt="Compute “down”. Is the host dead?" width="150"></a> | **PG-06**<br>[Compute “down”. Is the host dead?](categories/compute/compute-down-is-not-host-down.md) | “Down” is a missing heartbeat, not a dead host. Prove it before you act. | [recovery/…](../runbooks/recovery/nova-compute-down-instances-still-running/)<br>`lab-verified` |
| <a href="categories/compute/fence-before-evacuate.md"><img src="dist/pg-07-fence-before-evacuate.png" alt="Fence before you evacuate" width="150"></a> | **PG-07**<br>[Fence before you evacuate](categories/compute/fence-before-evacuate.md) | The precondition for evacuation is fencing, not a missing heartbeat. | [recovery/…](../runbooks/recovery/compute-host-failure-fence-before-evacuate/)<br>`lab-verified` |
| <a href="categories/compute/disabled-or-down.md"><img src="dist/pg-08-disabled-or-down.png" alt="Disabled or down? Two fields" width="150"></a> | **PG-08**<br>[Disabled or down? Two fields](categories/compute/disabled-or-down.md) | Disabled is a scheduling decision. Down is a belief about liveness. | [scheduling/…](../runbooks/scheduling/compute-service-disabled-or-forced-down/)<br>`lab-verified` |
| <a href="categories/compute/emptying-a-host-for-maintenance.md"><img src="dist/pg-09-emptying-a-host-for-maintenance.png" alt="Emptying a host for patching?" width="150"></a> | **PG-09**<br>[Emptying a host for patching?](categories/compute/emptying-a-host-for-maintenance.md) | After a libvirt or QEMU patch, instances can move onto the host, not back. Plan the order. | [migration/…](../runbooks/migration/moving-instances-off-a-host-for-maintenance/)<br>`lab-verified` |
| <a href="categories/compute/live-migration-never-completes.md"><img src="dist/pg-23-live-migration-never-completes.png" alt="Live migration never completes?" width="150"></a> | **PG-23**<br>[Live migration never completes?](categories/compute/live-migration-never-completes.md) | Watch whether the remaining memory goes down. If it hovers, waiting will not help. | [migration/…](../runbooks/migration/live-migration-never-completes-or-times-out/)<br>`draft` |
| <a href="categories/compute/steal-time-on-pinned-cpus.md"><img src="dist/pg-34-steal-time-on-pinned-cpus.png" alt="Steal time on pinned CPUs?" width="150"></a> | **PG-34**<br>[Steal time on pinned CPUs?](categories/compute/steal-time-on-pinned-cpus.md) | Live migration moves the symptom, not the cause. The cause is on the host. | [migration/…](../runbooks/migration/cpu-steal-on-pinned-instances/)<br>`lab-verified` |
| <a href="categories/compute/after-a-compute-reboot.md"><img src="dist/pg-35-after-a-compute-reboot.png" alt="After a reboot, VMs stay off?" width="150"></a> | **PG-35**<br>[After a reboot, VMs stay off?](categories/compute/after-a-compute-reboot.md) | A reboot brings back what is written down. Nova does not restart guests by default. | [recovery/…](../runbooks/recovery/after-a-compute-reboot-instances-shutoff-or-without-network/)<br>`lab-verified` |
| <a href="categories/compute/compute-renamed-or-re-added.md"><img src="dist/pg-36-compute-renamed-or-re-added.png" alt="Compute renamed or re-added?" width="150"></a> | **PG-36**<br>[Compute renamed or re-added?](categories/compute/compute-renamed-or-re-added.md) | Three records must agree. A healthy container proves nothing: the log says which one differs. | [scheduling/…](../runbooks/scheduling/compute-renamed-or-re-registered-resource-provider-conflict/)<br>`draft` |

### Networking

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/networking/active-but-no-ip.md"><img src="dist/pg-10-active-but-no-ip.png" alt="ACTIVE, but no IP address?" width="150"></a> | **PG-10**<br>[ACTIVE, but no IP address?](categories/networking/active-but-no-ip.md) | ACTIVE means Nova did its job. It says nothing about the network of the guest. | [networking/…](../runbooks/networking/new-instance-gets-no-ip-dhcp-agents-down/)<br>`lab-verified` |
| <a href="categories/networking/unreachable-from-outside.md"><img src="dist/pg-11-unreachable-from-outside.png" alt="Reachable inside, not outside?" width="150"></a> | **PG-11**<br>[Reachable inside, not outside?](categories/networking/unreachable-from-outside.md) | Each check rules out one cause. Go through them in order. | [networking/…](../runbooks/networking/instance-unreachable-from-outside/)<br>`lab-verified` |
| <a href="categories/networking/ping-works-transfers-stall.md"><img src="dist/pg-12-ping-works-transfers-stall.png" alt="Ping works, big transfers stall?" width="150"></a> | **PG-12**<br>[Ping works, big transfers stall?](categories/networking/ping-works-transfers-stall.md) | A green ping proves small packets pass. Test the largest one the network promises. | [networking/…](../runbooks/networking/tunnel-mtu-mismatch-large-packets-dropped/)<br>`lab-verified` |
| <a href="categories/networking/whole-compute-lost-network.md"><img src="dist/pg-24-whole-compute-lost-network.png" alt="One compute's VMs lost network?" width="150"></a> | **PG-24**<br>[One compute's VMs lost network?](categories/networking/whole-compute-lost-network.md) | Monitoring built on Nova states cannot see a data-plane outage. | [networking/…](../runbooks/networking/ovs-vswitchd-down-on-compute/)<br>`lab-verified` |
| <a href="categories/networking/security-group-rule-has-no-effect.md"><img src="dist/pg-25-security-group-rule-has-no-effect.png" alt="Security group rule has no effect?" width="150"></a> | **PG-25**<br>[Security group rule has no effect?](categories/networking/security-group-rule-has-no-effect.md) | Groups add up, on a default deny. Read the rules before you blame the agent. | [networking/…](../runbooks/networking/security-group-rules-not-applied/)<br>`draft` |
| <a href="categories/networking/booted-without-its-ssh-key.md"><img src="dist/pg-37-booted-without-its-ssh-key.png" alt="Booted without its SSH key?" width="150"></a> | **PG-37**<br>[Booted without its SSH key?](categories/networking/booted-without-its-ssh-key.md) | An instance gets its identity at first boot. Miss it, and the damage outlives the outage. | [networking/…](../runbooks/networking/new-instance-boots-without-metadata/)<br>`lab-verified` |
| <a href="categories/networking/binding-failed-for-port.md"><img src="dist/pg-38-binding-failed-for-port.png" alt="Binding failed for port?" width="150"></a> | **PG-38**<br>[Binding failed for port?](categories/networking/binding-failed-for-port.md) | Nova names the host. Neutron must find a live agent, with the right mappings, under that exact name. | [networking/…](../runbooks/networking/port-binding-failed/)<br>`draft` |

### Storage

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/storage/volume-stuck-attaching-or-detaching.md"><img src="dist/pg-13-volume-stuck-attaching-or-detaching.png" alt="Volume stuck attaching or detaching?" width="150"></a> | **PG-13**<br>[Volume stuck attaching or detaching?](categories/storage/volume-stuck-attaching-or-detaching.md) | The hypervisor tells the truth about the instance. Trust it over both databases. | [volumes/…](../runbooks/volumes/volume-stuck-in-attaching-or-detaching/)<br>`lab-verified` |
| <a href="categories/storage/volume-in-use-by-a-missing-instance.md"><img src="dist/pg-14-volume-in-use-by-a-missing-instance.png" alt="In-use by a VM that is gone?" width="150"></a> | **PG-14**<br>[In-use by a VM that is gone?](categories/storage/volume-in-use-by-a-missing-instance.md) | A record is stale only when the hypervisor agrees. Check the host before you change the database. | [volumes/…](../runbooks/volumes/stale-volume-attachment-after-instance-deleted-or-evacuated/)<br>`lab-verified` |
| <a href="categories/storage/extended-but-same-size-inside.md"><img src="dist/pg-39-extended-but-same-size-inside.png" alt="Extended, same size inside?" width="150"></a> | **PG-39**<br>[Extended, same size inside?](categories/storage/extended-but-same-size-inside.md) | Find the last stage that happened before you repeat the first. | [volumes/…](../runbooks/volumes/extend-in-use-volume-guest-sees-old-size/)<br>`draft` |
| <a href="categories/storage/volume-stuck-in-creating.md"><img src="dist/pg-40-volume-stuck-in-creating.png" alt="Volume stuck in creating?" width="150"></a> | **PG-40**<br>[Volume stuck in creating?](categories/storage/volume-stuck-in-creating.md) | No host: the scheduler. A host set: the backend. Cinder's message, or its log, says the rest. | [volumes/…](../runbooks/volumes/volume-stuck-in-creating-or-error-after-create/)<br>`lab-verified` |
| <a href="categories/storage/volume-will-not-delete.md"><img src="dist/pg-41-volume-will-not-delete.png" alt="Volume will not delete?" width="150"></a> | **PG-41**<br>[Volume will not delete?](categories/storage/volume-will-not-delete.md) | A volume that refuses to go may still be in use. Find the user before forcing anything. | [volumes/…](../runbooks/volumes/volume-stuck-in-deleting-or-error-deleting/)<br>`lab-verified` |

### Control plane

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/control-plane/control-plane-down.md"><img src="dist/pg-15-control-plane-down.png" alt="Control plane down: what runs?" width="150"></a> | **PG-15**<br>[Control plane down: what runs?](categories/control-plane/control-plane-down.md) | A control-plane outage is not a workload outage. Protect what runs, then repair. | [diagnostics/…](../runbooks/diagnostics/control-plane-down-what-still-works-for-instances/)<br>`lab-verified` |
| <a href="categories/control-plane/rpc-timeouts-everywhere.md"><img src="dist/pg-16-rpc-timeouts-everywhere.png" alt="MessagingTimeout everywhere?" width="150"></a> | **PG-16**<br>[MessagingTimeout everywhere?](categories/control-plane/rpc-timeouts-everywhere.md) | Computes reported down are a symptom here. Read every RabbitMQ node before you reset anything. | [recovery/…](../runbooks/recovery/rabbitmq-partition-or-alarm-rpc-timeouts/)<br>`lab-verified` |
| <a href="categories/control-plane/galera-lost-quorum.md"><img src="dist/pg-17-galera-lost-quorum.png" alt="APIs fail on database errors?" width="150"></a> | **PG-17**<br>[APIs fail on database errors?](categories/control-plane/galera-lost-quorum.md) | The data is at risk only during the recovery. Know the most advanced node before you bootstrap. | [recovery/…](../runbooks/recovery/galera-cluster-lost-quorum-database-unavailable/)<br>`lab-verified` |
| <a href="categories/control-plane/api-returns-503.md"><img src="dist/pg-26-api-returns-503.png" alt="The API answers 503?" width="150"></a> | **PG-26**<br>[The API answers 503?](categories/control-plane/api-returns-503.md) | A 503 from HAProxy is a messenger. Find out why the backends fail their check. | [recovery/…](../runbooks/recovery/api-returns-503-haproxy-backend-down-or-vip-flapping/)<br>`lab-verified` |
| <a href="categories/control-plane/401-with-a-valid-token.md"><img src="dist/pg-27-401-with-a-valid-token.png" alt="401 with a valid token?" width="150"></a> | **PG-27**<br>[401 with a valid token?](categories/control-plane/401-with-a-valid-token.md) | A fresh token hides the problem. Test with one older than the token cache. | [recovery/…](../runbooks/recovery/keystone-401-for-every-request-fernet-keys-or-clock/)<br>`lab-verified` |
| <a href="categories/control-plane/database-connections-exhausted.md"><img src="dist/pg-28-database-connections-exhausted.png" alt="Out of database connections?" width="150"></a> | **PG-28**<br>[Out of database connections?](categories/control-plane/database-connections-exhausted.md) | Three limits, three messages. The message tells you where to look first. | [recovery/…](../runbooks/recovery/database-too-many-connections-or-pool-exhausted/)<br>`draft` |
| <a href="categories/control-plane/conductor-or-scheduler-down.md"><img src="dist/pg-42-conductor-or-scheduler-down.png" alt="Conductor or scheduler down?" width="150"></a> | **PG-42**<br>[Conductor or scheduler down?](categories/control-plane/conductor-or-scheduler-down.md) | With the conductor gone, every compute looks down. Nothing is wrong on the hosts. | [recovery/…](../runbooks/recovery/nova-conductor-or-scheduler-down-what-still-works/)<br>`lab-verified` |
| <a href="categories/control-plane/provisioning-fails-everywhere.md"><img src="dist/pg-43-provisioning-fails-everywhere.png" alt="Provisioning fails everywhere?" width="150"></a> | **PG-43**<br>[Provisioning fails everywhere?](categories/control-plane/provisioning-fails-everywhere.md) | When everything fails at once, look at what everything shares. | [diagnostics/…](../runbooks/diagnostics/vm-creation-fails-platform-wide-check-shared-dependencies/)<br>`draft` |

### Production operations

| | Memo | Operational lesson | Runbook |
|---|---|---|---|
| <a href="categories/production-operations/before-restarting-an-agent.md"><img src="dist/pg-18-before-restarting-an-agent.png" alt="Restarting an agent on a compute?" width="150"></a> | **PG-18**<br>[Restarting an agent on a compute?](categories/production-operations/before-restarting-an-agent.md) | Before a restart, know which process carries the workload, and what keeps it alive. | [lifecycle/…](../runbooks/lifecycle/restarting-nova-libvirt-does-not-stop-instances/)<br>`lab-verified` |
| <a href="categories/production-operations/trace-one-request.md"><img src="dist/pg-19-trace-one-request.png" alt="A build failed. Which service?" width="150"></a> | **PG-19**<br>[A build failed. Which service?](categories/production-operations/trace-one-request.md) | The last service that logged the request id is where it stopped. Start there. | [diagnostics/…](../runbooks/diagnostics/what-a-vm-creation-traverses-and-tracing-by-request-id/)<br>`lab-verified` |
| <a href="categories/production-operations/cleaning-up-stale-records.md"><img src="dist/pg-20-cleaning-up-stale-records.png" alt="Cleaning up stale records?" width="150"></a> | **PG-20**<br>[Cleaning up stale records?](categories/production-operations/cleaning-up-stale-records.md) | Project tools first, the database last. And first of all: is this record true? | [lifecycle/…](../runbooks/lifecycle/stale-records-stuck-instances-orphan-ports-attachments/)<br>`lab-verified` |
| <a href="categories/production-operations/logs-do-not-line-up.md"><img src="dist/pg-44-logs-do-not-line-up.png" alt="Logs do not line up?" width="150"></a> | **PG-44**<br>[Logs do not line up?](categories/production-operations/logs-do-not-line-up.md) | Before trusting a timeline built from several hosts, compare their clocks. | [diagnostics/…](../runbooks/diagnostics/compute-clock-skew/)<br>`lab-verified` |

<!-- catalog:end -->

## 📌 Not covered yet

A memo is only written from a runbook that documents the subject. These topics were considered for the first
collection and left out, rather than filled with guesses.

**No source yet.** They need a runbook first, from a real occurrence:

| Topic | Where it stands |
|---|---|
| Live migration fails at the pre-check (CPU model, shared storage assumptions) | Listed under *Pages wanted next* in the [VM runbooks](../runbooks/#-pages-wanted-next) |
| Floating IP does not answer with ML2/OVN | Same list. The ML2/OVS case is in PG-11 |
| Shelve and unshelve problems | Same list |
| Multi-attach volumes | Same list |
| Storage backend outage: Cinder backend unavailable, storage capacity exhausted | Same list ("storage outage"). Storage-backend-only problems are out of the runbooks' scope |
| Multipath problems | Only a log-reading guide exists (`draft`): not enough for a memo |
| CPU overcommitment, hypervisor out of resources | No runbook. Allocation ratios appear only as a cause in PG-02 |
| Before applying a configuration change, before patching: the general checklist | No runbook. PG-09 and PG-18 cover two specific cases |

**A source exists, a memo does not.** Good candidates for a first contribution. This list is generated: it is every
runbook, outside the `logs/` reading guides, that no memo is written from or cites.

<!-- candidates:start -->
None at the moment: every runbook has its memo.
<!-- candidates:end -->

Memos written from a `draft` runbook are welcome: the status is printed on the memo.

## 🗂️ How content is organised

Content and presentation are separate. A memo is a small YAML file; the look comes from one template.

```text
categories/<category>/<slug>.yml   the source of a memo: its text, its diagram, its runbook, its LinkedIn kit
categories/<category>/<slug>.md    generated: the memo's page
templates/                         the template (memo.cjs), its styles (memo.css), the design tokens (tokens.css),
                                   and memo.yml, the starting point of a new memo
assets/                            vendored fonts and icons, the OzarLand mark
scripts/                           build.cjs (validate, render, generate), new-memo.cjs
dist/                              the exported images, 1080 × 1350, ready to post
LINKEDIN.md                        generated: every post title, caption and hashtag set in one place
DESIGN.md                          the visual identity and the rules of the template
```

## 🔧 Build it yourself

Requires Node.js 20 or later.

In the directory of this module, `docs/production/` of the repository of OzarLand Academy:

```bash
npm ci
```

```bash
npx playwright install chromium
```

```bash
npm run build
```

The build validates every memo, checks each runbook reference against the VM runbooks, `docs/runbooks/` next to this module
(the path, and that the status and release printed on the memo are the runbook's own), renders the images and
regenerates the pages, this catalog and `LINKEDIN.md`. It fails if a text is over its length budget or if anything
does not fit the canvas: the template never shrinks text to make it fit.

| Command | What it does |
|---|---|
| `npm run new -- <category> <slug>` | Creates a new memo source from the template, with the next number |
| `npm run build -- --only <slug>` | Renders one memo while you write it |
| `npm run validate` | Checks content and runbook references, renders nothing |
| `npm run build -- --scale 2` | Exports at 2160 × 2700 (not committed) |
| `npm run build -- --runbooks <dir>` | Checks the runbook references against another directory than `../runbooks` (the VM runbooks of this repository) |

## 🤝 Contributing

| | How |
|:-:|---|
| 🐛 | **Something is wrong, or your platform behaves differently:** [open an issue](https://github.com/OzarLand/ozarland-academy/issues/new). If the runbook is wrong too, the correction belongs [there first](https://github.com/OzarLand/ozarland-academy/issues/new?template=documentation-proposal.yml) |
| 💡 | **Propose a memo:** open an issue with the situation, the lesson and the runbook it would rest on |
| ✍️ | **Write a memo:** `npm run new`, fill in the YAML, build, open a pull request. No design tool needed |
| 🧱 | **No runbook for your lesson?** Share the problem you solved with the [*Problem solved* form](https://github.com/OzarLand/ozarland-academy/issues/new?template=problem-solved.yml) first, for a runbook. The memo follows |
| 💬 | **A question:** [start a discussion](https://github.com/OzarLand/ozarland/discussions/new?category=q-a) in `ozarland`, where all OzarLand discussions live |

> [!IMPORTANT]
> Rules that are not optional: every statement is backed by a runbook; the first checks are read-only;
> state-changing and destructive actions are flagged; the memo says where it was observed; no secrets, hostnames or
> addresses. Full guide: [CONTRIBUTING.md](CONTRIBUTING.md). Design rules: [DESIGN.md](DESIGN.md).

## 🌍 Part of OzarLand Academy

This module is the last stop of [OzarLand Academy](../), the learning path of
[OzarLand](https://github.com/OzarLand/ozarland): *a shared land for better OpenStack operations.* Each memo comes
from a page of the [VM runbooks](../runbooks/); the [Quick lab](../lab/) is where to try them, and the
[deployment patterns](../deploy/) and [Kolla-Ansible Academy](../day2/) explain the platform underneath.

## ⚖️ License

All content, documentation and code alike, is licensed under the Apache License 2.0 ([LICENSE](https://github.com/OzarLand/ozarland-academy/blob/main/LICENSE)). Reuse it
freely with attribution. See [licensing](https://github.com/OzarLand/ozarland/blob/main/docs/conventions/licensing.md).
The vendored fonts and icons keep their own licences: see [assets/index.md](https://github.com/OzarLand/ozarland-academy/blob/main/docs/production/assets/index.md).

OpenStack is a project of the OpenInfra Foundation community. OzarLand is an independent community initiative.

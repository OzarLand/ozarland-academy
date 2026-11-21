---
title: "OKD node and host operating system"
description: "The whole control plane, every OpenStack pod and every volume live on one virtual machine, okd-0."
---

# OKD node and host operating system

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- Two doors to the node: `oc debug node/okd-0` needs the API, SSH as
  `core` needs only sshd. Keep the SSH path tested.
- The host is an image-based system (CentOS Stream CoreOS): no package
  installation, every durable change is a MachineConfig and a reboot.
- One 150 GiB partition holds images, logs, etcd and every OpenStack
  volume; 1 GiB of memory is reserved for host services that used
  3.9 to 4.4 GiB when measured (2026-11-12).
- Evidence is short-lived: events 3 hours, API audit log about 10
  hours, container logs gone with the pod, journal about two weeks.
- Cordon only blocks new pods; a drain of the single node is an outage
  with no benefit.

The whole control plane, every OpenStack pod and every volume live on one
virtual machine, `okd-0`. This file records how that machine is entered,
what its operating system is, how kubelet and CRI-O are inspected, where
the disk and the memory go, and what cordon means when there is no second
node. Commands run on the bastion as the cluster administrator; `node`
is a shell on the OKD node:

```bash
node() { ssh core@192.168.130.10 "$@"; }
```

## Entries

### How do I get a shell on the node: `oc debug node` or SSH as `core`?

**Context**: any host-level check (disk, journal, `crictl`). The two
doors do not depend on the same things, which matters during an
incident.

**How**:

**[READ-ONLY]**

```bash
# door 1: through the API (needs the API, the scheduler and kubelet)
oc debug node/okd-0 -q -- chroot /host sh -c 'id; hostname; cat /proc/1/comm'
oc debug node/okd-0 --dry-run=client -o yaml | grep -E 'image:|hostNetwork|hostPID|hostIPC|privileged|path:'

# door 2: SSH from the bastion (needs only sshd on the node)
node 'id; sudo -n true && echo sudo-ok'
```

**Observed on the lab** (2026-11-12):

```text
uid=0(root) gid=0(root) groups=0(root) context=system_u:system_r:spc_t:s0
okd-0
systemd
    image: quay.io/okd/scos-content@sha256:<digest>
      privileged: true
  hostIPC: true
  hostNetwork: true
  hostPID: true
      path: /
uid=1000(core) gid=1000(core) groups=1000(core),4(adm),10(wheel),16(sudo),190(systemd-journal) ...
sudo-ok
```

`oc debug node` took 1.3 s (the tools image is already on the node) and
left no pod behind. Without `chroot /host` the shell is inside the tools
image (CentOS Stream 9 userland) with the host mounted on `/host`; with
it, the commands are the host's own. The debug pod is created in the
current project (`openstack` on the bastion) and prints a pod security
warning that is expected: it is a privileged pod.

**Why / how it works**: `oc debug node` creates a privileged pod with the
host PID, network and IPC namespaces and the host root mounted. It needs
a working API server, scheduler, kubelet and CRI-O. SSH as `core` uses
the public key installed by the `99-master-ssh` MachineConfig and needs
none of them: it is the only door left when the API is down, which on a
single node happens at every API server restart. Kolla-Ansible
equivalent: SSH to a controller, with `oc debug` being a `docker run
--privileged --pid host -v /:/host` shortcut.

**Pitfalls**:

- When the API is down, `oc debug` is down too. Keep the SSH path tested;
  on this lab the bastion still had the host key of a previous
  installation and refused to connect until `ssh-keygen -R
  192.168.130.10` was run.
- SSH access leaves no trace in the cluster on this version (no `ssh`
  annotation appeared on the node after the sessions of this page); the
  only record is the host journal (`journalctl -u sshd`).
- The debug pod lands in the current project. To keep it out of
  `openstack`, add `--to-namespace=default` (verified).
- A file changed by hand under `/etc` survives reboots but is a
  configuration drift: if the file is owned by a MachineConfig, the
  daemon marks the node `Degraded` at the next check.

**See also**:
[Node and OKD troubleshooting](../troubleshooting/node-and-okd.md),
[API health](okd-cluster-health-and-etcd.md#is-the-api-healthy-and-fast-right-now)

### What is the host operating system, and why can I not install a package?

**Context**: first contact with the node, or the reflex of running
`dnf install` to get a tool.

**How**:

**[READ-ONLY]**

```bash
node 'head -3 /etc/os-release; uname -r; sudo rpm-ostree status'
node 'lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT; df -h / /var /boot'
node 'touch /usr/x; rpm -qa | wc -l; rpm -q cri-o crun openvswitch3.5 podman chrony'
node 'journalctl --list-boots --no-pager'
```

**Observed on the lab** (2026-11-12):

```text
NAME="CentOS Stream CoreOS"
VERSION="10.0.20260806-0 (Coughlan)"
6.12.0-254.el10.x86_64
State: idle
Deployments:
● ostree-unverified-registry:quay.io/okd/scos-content@sha256:<digest>
                  Version: 10.0.20260806-0 (2026-08-08T13:47:16Z)
vda      150G disk
├─vda1     1M part
├─vda2   127M part vfat
├─vda3   384M part ext4    /boot
└─vda4 149.5G part xfs     /sysroot
composefs       5.6M  5.6M     0 100% /
/dev/vda4       150G   46G  105G  31% /var
touch: cannot touch '/usr/x': Read-only file system
496
cri-o-1.35.5-1.el10s.x86_64  crun-1.28-1.el10.x86_64  openvswitch3.5-3.5.3-5.el10s.x86_64
podman-6.0.2-1.el10.x86_64  chrony-4.8-2.el10.x86_64
```

One deployment only (no rollback entry): the node was installed, pivoted
once to the release's operating system image and never updated. The
journal shows five boots: three in the first three minutes of the
installation (live installer, first boot, pivot to the release image),
one at 23:57 and one at 00:32 UTC during the lab validation. The first
boot ran kernel 6.12.0-150, the current one 6.12.0-254: the installer
image is older than the release.

**Why / how it works**: CentOS Stream CoreOS is an image-based system.
`/usr` is a read-only image named by a digest that belongs to the OKD
release; `/etc` and `/var` are the only writable places and both sit on
the single XFS partition. The operating system is updated by the machine
config operator together with the cluster, never by `dnf`. Tools are
brought by containers (`oc debug`, `toolbox`, `podman run`). Kolla-Ansible
equivalent: none — there the host is an ordinary distribution that the
operator patches; here the host is part of the product.

**Pitfalls**:

- `rpm-ostree install <pkg>` works technically (layering) but makes the
  node differ from the image the machine config operator expects; do not
  do it on the lab.
- There is one partition for the operating system, container images,
  container logs, etcd and every OpenStack volume. See
  [where the disk goes](#where-does-the-disk-space-go-on-the-node).
- `df /` shows a 5.6 MB composefs at 100 %: normal, it is the read-only
  image metadata, not the disk.
- The kubelet package is named `openshift-kubelet` (`rpm -q kubelet`
  answers "not installed").

**See also**: [OKD in brief](../concepts/07-okd-in-brief.md),
[OKD upgrade](../lifecycle/07-okd-upgrade.md)

### What does a MachineConfig contain, and what would changing one do?

**Context**: any wish to change a host file, a systemd unit, a kernel
argument or a kubelet setting durably. Read this before, because the
change mechanism reboots the only node.

**How**:

**[READ-ONLY]**

```bash
oc get mcp
oc get mc
MC=$(oc get mcp master -o jsonpath='{.status.configuration.name}')
oc get mc "$MC" -o jsonpath='{.spec.kernelArguments}{"\n"}{.spec.kernelType} fips={.spec.fips}{"\n"}'
oc get mc "$MC" -o jsonpath='{range .spec.config.systemd.units[*]}{.name} {.enabled}{"\n"}{end}'
oc get mc "$MC" -o jsonpath='{range .spec.config.storage.files[*]}{.path}{"\n"}{end}' | wc -l
oc get mc 50-masters-chrony-configuration -o jsonpath='{range .spec.config.storage.files[*]}{.path}{"\n"}{end}'
oc get node okd-0 -o jsonpath='{.metadata.annotations}' | python3 -c 'import json,sys; [print(k.split("/")[1], "=", v) for k, v in json.load(sys.stdin).items() if "machineconfig" in k]'
oc get kubeletconfig,containerruntimeconfig
```

**Observed on the lab** (2026-11-12):

```text
master   rendered-master-<hash>   True   False   False   1   1   1   0   15h
worker   rendered-worker-<hash>   True   False   False   0   0   0   0   15h
["systemd.unified_cgroup_hierarchy=1","cgroup_no_v1=\"all\""]
default fips=false
52                                  # files written on the host
/etc/chrony.conf
currentConfig = rendered-master-<hash>
desiredConfig = rendered-master-<hash>
state = Done
controlPlaneTopology = SingleReplica
No resources found                  # no KubeletConfig, no ContainerRuntimeConfig
```

Besides the platform's own configs (`00-master`, `01-master-kubelet`,
`01-master-container-runtime`, `97/98-master-generated-kubelet`,
`99-master-generated-registries`, `99-master-ssh`), four come from the
installation of this lab: `50-masters-chrony-configuration`
(`/etc/chrony.conf`), `50-master-dnsmasq-configuration` (a local dnsmasq
and its NetworkManager hook, standard for single-node), and
`50-masters-iscsi-nic-reapply` (one systemd unit). The node carries both
the `master` and `worker` roles but belongs only to the `master` pool.

**Why / how it works**: the machine config controller merges every
MachineConfig of a pool into one `rendered-<pool>-<hash>`. The machine
config daemon on the node compares it with the node's `currentConfig`;
when they differ it writes the files and reboots. On a multi-node
cluster it cordons and drains first; on a single-node control plane it
skips the drain. The practical effect is: the whole platform and
OpenStack control plane stop for the duration of a reboot (measured:
about 6 minutes until every OpenStack pod is ready, 7 until the pool
reports `Updated`, see [OKD node maintenance](okd-node-maintenance.md)).
A `KubeletConfig` or `ContainerRuntimeConfig` resource is the supported
way to change kubelet or CRI-O settings; each generates a MachineConfig
and therefore a reboot.
Kolla-Ansible equivalent: the host part of the inventory and
`kolla-ansible bootstrap-servers`, except that here drift is detected and
the reboot is automatic.

**Pitfalls**:

- Creating or editing a MachineConfig is not a dry operation: the reboot
  starts 10 to 15 seconds later. To prepare several changes, pause the pool
  first (`oc patch mcp master --type merge -p '{"spec":{"paused":true}}'`),
  and remember a paused pool also blocks the automatic rotation of some
  node certificates.
- `oc get mc` shows `rendered-worker-...` although there is no worker:
  it is unused.
- This entry is the read-only study. A MachineConfig was applied and
  removed later the same day: the mechanism, the timeline and the repair
  needed on the compute node are in
  [OKD node maintenance](okd-node-maintenance.md).

**See also**:
[OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md),
[Operating system entry](#what-is-the-host-operating-system-and-why-can-i-not-install-a-package)

### How is kubelet configured, and where are its logs?

**Context**: a pod that does not start, a node `NotReady`, or the need
to know an effective kubelet setting.

**How**:

**[READ-ONLY]**

```bash
node 'systemctl status kubelet --no-pager | head -9; systemctl cat kubelet --no-pager | grep -E "^(ExecStart|Environment|Restart)|--"'
# effective configuration, defaults included (the file on disk shows only overrides)
oc get --raw /api/v1/nodes/okd-0/proxy/configz | python3 -c '
import json, sys
d = json.load(sys.stdin)["kubeletconfig"]
for k in ("maxPods", "podPidsLimit", "systemReserved", "kubeReserved", "enforceNodeAllocatable",
          "evictionHard", "evictionSoft", "evictionPressureTransitionPeriod",
          "imageGCHighThresholdPercent", "imageGCLowThresholdPercent", "imageMinimumGCAge",
          "containerLogMaxSize", "containerLogMaxFiles", "cgroupDriver", "cpuManagerPolicy",
          "shutdownGracePeriod", "serializeImagePulls", "rotateCertificates", "serverTLSBootstrap"):
    print(k, "=", d.get(k))'
# logs: by the journal, or through the API
node 'sudo journalctl -u kubelet --since "-1h" --no-pager -o cat | cut -c1 | sort | uniq -c'
node 'sudo journalctl -u kubelet --since "-6h" --no-pager -o cat | grep -E "^[EW]" | sed -E "s/^([EW])[0-9]+ [0-9:.]+ +[0-9]+ ([a-z_.]+:[0-9]+)\].*/\1 \2/" | sort | uniq -c | sort -rn | head -5'
oc adm node-logs okd-0 -u kubelet --since=-10m | tail -3
```

**Observed on the lab** (2026-11-12):

```text
     Active: active (running) since Thu 2026-11-12 00:32:47 UTC; 11h ago
     Memory: 641.8M (peak: 701.9M)
maxPods = 250
podPidsLimit = 4096
systemReserved = {'cpu': '500m', 'ephemeral-storage': '1Gi', 'memory': '1Gi'}
kubeReserved = None
enforceNodeAllocatable = ['pods']
evictionHard = {'imagefs.available': '15%', 'imagefs.inodesFree': '5%', 'memory.available': '100Mi', 'nodefs.available': '10%', 'nodefs.inodesFree': '5%'}
evictionSoft = None
evictionPressureTransitionPeriod = 5m0s
imageGCHighThresholdPercent = 85
imageGCLowThresholdPercent = 80
imageMinimumGCAge = 2m0s
containerLogMaxSize = 50Mi
containerLogMaxFiles = 5
cgroupDriver = systemd
cpuManagerPolicy = none
shutdownGracePeriod = 0s
serializeImagePulls = False
rotateCertificates = True
serverTLSBootstrap = True
     14 E                           # last hour: 14 errors, 88 info, 1 warning
     88 I
      1 W
    131 E upgradeaware.go:427       # last 6 hours, by source line
     22 W manager.go:1172
      8 E upgradeaware.go:441
      6 E status_manager.go:1045
```

Kubelet has run without restart since the last boot. The dominant error,
`upgradeaware.go:427 Error proxying data from client to backend ...
broken pipe`, is produced each time an `oc exec` or `oc rsh` session
ends: it is the noise of the operator's own commands (and of the
knowledge base work), not a fault.

**Why / how it works**: kubelet is a systemd unit of the host
(`/etc/systemd/system/kubelet.service` plus drop-ins, all written by
MachineConfig), started through `kubenswrapper`, which is also the syslog
identifier of its journal lines. Its configuration file is
`/etc/kubernetes/kubelet.conf`; the reserved resources come from
`/etc/node-sizing.env`. `/configz` returns the merged, effective values.
`oc adm node-logs` asks kubelet itself to read the journal
(`enableSystemLogQuery`), so it works only while the API and kubelet are
up. Kolla-Ansible equivalent: the Docker daemon plus the `restart:
unless-stopped` policy; kubelet is what restarts containers here.

**Pitfalls**:

- `shutdownGracePeriod = 0s`: a host shutdown does not give pods a
  graceful stop through kubelet. Galera, RabbitMQ and the OVN databases
  are stopped by systemd killing containers. They recovered after the
  two reboots of the validation, but this is why a clean stop of the
  lab scales nothing down by itself.
- `oc adm node-logs okd-0 -u crio --since=-30m` printed `-- No entries
  --` while the same query over SSH returned lines: the API path filters
  differently by unit. Use SSH when the result looks empty.
- `oc adm node-logs` has no `-k` flag in this version; kernel messages
  are read with `--path=journal` (raw files) or over SSH with
  `journalctl -k`.
- Restarting kubelet (`systemctl restart kubelet`) does not restart the
  containers, but makes the node `NotReady` for some seconds and
  restarts every probe timer. Not tested on 2026-11-12 (forbidden before
  the certificate rotation).

**See also**: [Logs](../operations/02-logs.md),
[Pod pending or CrashLoop](../troubleshooting/pod-pending-or-crashloop.md)

### How much is reserved for the system, and when would kubelet evict pods?

**Context**: capacity planning on one 32 GiB node, or understanding a
`MemoryPressure` / `DiskPressure` condition.

**How**:

**[READ-ONLY]**

```bash
oc get node okd-0 -o jsonpath='{.status.capacity}{"\n"}{.status.allocatable}{"\n"}'
oc get node okd-0 -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
node 'cat /etc/node-sizing.env /etc/node-sizing-enabled.env'
node 'cat /sys/fs/cgroup/kubepods.slice/memory.max /sys/fs/cgroup/kubepods.slice/memory.current /sys/fs/cgroup/system.slice/memory.current'
node 'free -m; swapon --show | wc -l; sysctl vm.overcommit_memory vm.panic_on_oom'
# what kubelet itself measures (this is what eviction uses)
oc get --raw /api/v1/nodes/okd-0/proxy/stats/summary | python3 -c '
import json, sys
n = json.load(sys.stdin)["node"]
print("workingSet GiB", round(n["memory"]["workingSetBytes"] / 2**30, 1), "available GiB", round(n["memory"]["availableBytes"] / 2**30, 1))
for c in n["systemContainers"]:
    print(c["name"], round(c["memory"]["workingSetBytes"] / 2**20), "MiB")'
```

**Observed on the lab** (2026-11-12):

```text
{"cpu":"16","ephemeral-storage":"156695532Ki","memory":"32856704Ki","pods":"250"}
{"cpu":"15500m","ephemeral-storage":"143336860229","memory":"31705728Ki","pods":"250"}
MemoryPressure=False KubeletHasSufficientMemory
DiskPressure=False KubeletHasNoDiskPressure
PIDPressure=False KubeletHasSufficientPID
Ready=True KubeletReady
SYSTEM_RESERVED_MEMORY=1Gi  SYSTEM_RESERVED_CPU=500m  SYSTEM_RESERVED_ES=1Gi
NODE_SIZING_ENABLED=false
32571523072     # kubepods.slice memory.max    = 30.3 GiB
26530582528     # kubepods.slice memory.current = 24.7 GiB (page cache included)
4220813312      # system.slice memory.current   = 3.9 GiB
Mem:   32086 total   19933 used   1045 free   11778 buff/cache   12153 available
0               # no swap
vm.overcommit_memory = 1
workingSet GiB 18.5 available GiB 12.9
kubelet 589 MiB
runtime 2518 MiB
misc 3433 MiB
pods 19383 MiB
```

Allocatable memory is capacity minus 1 GiB reserved minus the 100 MiB
hard eviction threshold. The system slice really uses 3.9 GiB (CRI-O
2.8 GiB with its page cache, kubelet 0.6 GiB), four times what is
reserved for it. With every pod running, 12.9 GiB are still available.

The figure of `system.slice` is a reading at one moment, not a constant.
`memory.current` counts the page cache charged to the slice, and CRI-O
is charged for the image layers it writes. Readings of the same file on
this node:

| Date (UTC) | `system.slice` `memory.current` | Context |
|---|---|---|
| 2026-11-12 11:45 | 4220813312 (3.9 GiB) | Node up for 11 hours; CRI-O 2.8 GiB, kubelet 0.6 GiB (output above) |
| 2026-11-12 12:26 | 4742664192 (4.4 GiB) | Same boot, 40 minutes later; the figure quoted in the [workloads file](okd-workloads-and-resources.md) |
| 2026-11-14 07:44 | 17172406272 (16.0 GiB) | 7 minutes after a boot in which CRI-O pulled every image again; 14.0 GiB of it is page cache (`file` in `memory.stat`) |
| 2026-11-14 07:47 | 10679451648 (9.9 GiB) | 10 minutes after the same boot; page cache 8.0 GiB, anonymous memory 0.8 GiB, kernel memory 0.7 GiB; CRI-O 9.0 GiB, kubelet 0.5 GiB |

The two readings of 2026-11-12 are the same measurement taken twice,
not two methods. The part that cannot be reclaimed (`anon` plus `kernel`
in `/sys/fs/cgroup/system.slice/memory.stat`) was 1.5 GiB on 2026-11-14;
it was not read on 2026-11-12, and no reading was taken on 2026-11-14
once the page cache had settled. In every reading the slice is above
the 1 GiB reserved for it.

**Why / how it works**: pods live under the `kubepods.slice` cgroup,
whose `memory.max` is capacity minus the system reservation; host
services live under `system.slice` without a limit. Kubelet evicts pods
when its own measure of `memory.available` (capacity minus working set)
drops below 100 MiB, or when the filesystem has less than 10 % free
(15 % for the image filesystem, which is the same disk here). Eviction
order: pods using more than their request first, by priority, BestEffort
before Burstable. If memory is exhausted faster than kubelet's 10 s
housekeeping, the kernel OOM killer acts first, guided by the
`oom_score_adj` derived from the QoS class. Kolla-Ansible equivalent:
none; there, containers have no limit and the kernel OOM killer is the
only arbiter.

**Pitfalls**:

- The 1 GiB system reservation is a static default
  (`NODE_SIZING_ENABLED=false`); it does not protect the 3.9 to 4.4 GiB (2026-11-12) that
  host services really use. Pods can fill `kubepods.slice` up to
  30.3 GiB and push the host services into reclaim. Enabling automatic
  sizing needs a `KubeletConfig` with `autoSizingReserved: true`, hence a
  reboot; not tested.
- 10 % of a 150 GiB disk is 15 GiB: disk pressure eviction starts when
  15 GiB are still free. Image garbage collection starts earlier, at
  85 % used.
- `free` reports "used 19.9 GiB" and kubelet "working set 18.5 GiB":
  different definitions. Eviction uses kubelet's.
- There is no swap and `failSwapOn` is true: memory exhaustion is always
  an eviction or an OOM kill.
- Pressure stall information is not available on this kernel build
  (`/proc/pressure/*` does not exist), so `oc adm top` and Prometheus are
  the way to see pressure building.

**See also**:
[Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Workloads and resources](okd-workloads-and-resources.md)

### How do I inspect containers below Kubernetes with `crictl` and CRI-O?

**Context**: the API is down or slow and containers must still be
listed, their logs read or their state understood; or an image pull
problem.

**How**:

**[READ-ONLY]**

```bash
node 'systemctl status crio --no-pager | head -8; sudo crictl version'
node 'sudo crio status config | grep -E "^\s*(default_runtime|cgroup_manager|conmon_cgroup|pids_limit|log_size_max|root|runroot|storage_driver|internal_wipe|pause_image) "'
node 'sudo crictl info | python3 -c "import json,sys; print(json.load(sys.stdin)[\"status\"][\"conditions\"])"'
node 'sudo crictl pods | awk "NR>1{print \$4}" | sort | uniq -c; sudo crictl ps | wc -l; sudo crictl images | wc -l'
# one pod from the bottom: sandbox -> containers -> process, log file, cgroup
node 'P=$(sudo crictl pods --name keystone -q | head -1); sudo crictl ps --pod $P'
node 'C=$(sudo crictl ps --name keystone-api -q | head -1); sudo crictl inspect $C | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[\"info\"][\"pid\"], d[\"status\"][\"logPath\"], d[\"info\"][\"runtimeSpec\"][\"linux\"][\"cgroupsPath\"])"'
node 'C=$(sudo crictl ps --name keystone-api -q | head -1); sudo crictl logs --tail 2 $C; sudo crictl stats $C'
node 'sudo journalctl -u crio --since "-6h" --no-pager -o cat | grep -o "level=[a-z]*" | sort | uniq -c'
```

**Observed on the lab** (2026-11-12):

```text
     Active: active (running) since Thu 2026-11-12 00:32:46 UTC; 11h ago
RuntimeName:  cri-o
RuntimeVersion:  1.35.5
    default_runtime = "crun"
    cgroup_manager = "systemd"
    conmon_cgroup = "pod"
    pids_limit = -1
    log_size_max = -1
  root = "/var/lib/containers/storage"
  runroot = "/run/containers/storage"
  storage_driver = "overlay"
  internal_wipe = true
[{'status': True, 'type': 'RuntimeReady'}, {'status': True, 'type': 'NetworkReady'}]
    242 Ready                       # pod sandboxes
    147 NotReady                    # finished or replaced sandboxes kept for their logs
200 running containers, 150 images
<pid> /var/log/pods/openstack_keystone-<hash>_<pod uid>/keystone-api/0.log kubepods-besteffort-pod<pod uid>.slice:crio:<container id>
    757 level=info                  # CRI-O journal, 6 hours
     10 level=warning
```

Images by origin: 84 from the OKD release, 29 OpenStack service images,
26 OpenStack operator images and bundles, a few for cert-manager, MetalLB
and the catalog. The warnings of CRI-O are of two harmless kinds:
`Skipping invalid sysctl ... not allowed with host net enabled` and
`Failed to get the status of process with PID ...` (a probe process that
ended before being measured).

**Why / how it works**: kubelet talks to CRI-O on
`/var/run/crio/crio.sock`; CRI-O starts each container with `crun`, with
one `conmon` process per container that holds its output and writes the
log file under `/var/log/pods/<namespace>_<pod>_<uid>/<container>/`.
`oc logs` reads the same files through kubelet. `crictl` talks to the
same socket, so it shows the truth even when the API server is down — it
is how the static pods (etcd, API server) are debugged. Kolla-Ansible
equivalent: `docker ps`, `docker logs`, `docker inspect`, `docker stats`.

**Pitfalls**:

- Do not `crictl stop` or `crictl rm` a container to "restart" it:
  kubelet notices and recreates it, but the restart count and the events
  blame a crash. Delete the pod through the API instead; reserve `crictl`
  for static pods when the API is down.
- `crictl imagefsinfo` reports 3 MiB used: it measures only the
  `overlay-images` directory. The real size of images is in
  [where the disk goes](#where-does-the-disk-space-go-on-the-node).
- `sudo podman ps` shows nothing: podman and CRI-O share the image
  store, not the containers. `podman images` and `podman system df`
  are useful, `podman rmi` is dangerous (kubelet thinks the image is
  still there).
- The registry search list is `registry.access.redhat.com`, `docker.io`
  for unqualified names; every image of this lab is fully qualified.
- Restarting CRI-O (`systemctl restart crio`) is survivable (containers
  keep running under conmon) but was not tested on 2026-11-12.

**See also**: [Logs](../operations/02-logs.md),
[Control plane static pods](okd-cluster-health-and-etcd.md#where-does-the-control-plane-itself-run-and-what-are-revisions)

### Where does the disk space go on the node?

**Context**: the disk fills, a `DiskPressure` condition appears, or a
size must be planned. Everything shares one 150 GiB partition.

**How**:

**[READ-ONLY]**

```bash
node 'df -h /var; df -i /var | tail -1'
node 'for d in /var/lib/containers/storage /var/lib/kubelet/pods /var/lib/etcd /var/lib/openstack-lab-pv /var/log /var/log/kube-apiserver /var/log/pods /var/log/journal /var/lib/cni /sysroot/ostree; do sudo du -xsh $d; done'
node 'sudo podman system df'
node 'sudo sh -c "du -sh /var/log/pods/* | sort -h | tail -4"'
# ephemeral storage per pod (emptyDir + writable layer + logs), as kubelet accounts it
oc get --raw /api/v1/nodes/okd-0/proxy/stats/summary | python3 -c '
import json, sys
d = json.load(sys.stdin)
r = [(p.get("ephemeral-storage", {}).get("usedBytes", 0), p["podRef"]["namespace"] + "/" + p["podRef"]["name"]) for p in d["pods"]]
for e, name in sorted(r)[-5:]:
    print(round(e / 2**20), "MiB", name)'
```

**Observed on the lab** (2026-11-12, 16 hours after installation):

```text
/dev/vda4       150G   46G  105G  31% /var
/dev/vda4      78380480 517256 77863224    1% /var        # inodes
31G     /var/lib/containers/storage       # images and writable layers
6.6G    /var/lib/kubelet/pods             # emptyDir volumes
483M    /var/lib/etcd
1.2G    /var/lib/openstack-lab-pv         # all 12 OpenStack local volumes
2.9G    /var/log
2.3G    /var/log/kube-apiserver           # API audit log
389M    /var/log/pods                     # container logs, 183 directories
182M    /var/log/journal
647M    /var/lib/cni
2.3G    /sysroot/ostree                   # the operating system image
Images   151 total   125 active   32.05GB   9.511GB (30%) reclaimable
86M     /var/log/pods/openstack_memcached-0_<uid>
58M     /var/log/pods/openshift-marketplace_community-operators-<hash>_<uid>
271 MiB openshift-marketplace/community-operators-<hash>
1096 MiB openshift-monitoring/prometheus-k8s-0
3177 MiB openshift-console/downloads-<hash>
```

Two thirds of the used space are container images. The OpenStack data
itself (Galera, RabbitMQ, Glance, OVN databases, backups) is 1.2 GiB. The
largest single consumers after images are surprising: the `downloads` pod
of the console (3.2 GiB of client binaries in its writable layer), the
API audit log (2.3 GiB in 16 hours, capped by rotation) and Prometheus
(1.1 GiB in an emptyDir).

**Why / how it works**: kubelet watches two things on this single
filesystem. Image garbage collection starts at 85 % used and removes
unused images until 80 %; 9.5 GiB are reclaimable today (images of
completed jobs, operator bundles, a previous catalog index). Container
logs rotate at 50 MiB with 5 files per container. The audit log rotates
by size and count. The journal is persistent with default limits (10 %
of the filesystem, capped at 4 GiB). Local volumes have no size
enforcement at all: the capacity written in a PV is a label. Kolla-Ansible
equivalent: `/var/lib/docker` plus `/var/lib/docker/volumes` plus
`/var/log/kolla`, usually split over several mounts; here nothing is
split.

**Pitfalls**:

- Prometheus stores its data in an emptyDir: it is counted against the
  node, lost when the pod is deleted, and grows with retention (15 days
  by default). See the monitoring file.
- etcd shares the disk with image pulls and logs; a burst of writes
  (large image pull, log storm) raises etcd fsync latency. Watch it with
  the query in
  [etcd checks](okd-cluster-health-and-etcd.md#how-do-i-check-etcd-members-health-size-alarms-and-latency).
- A Glance image upload or a Galera growth eats the same free space as
  the platform: nothing stops an OpenStack volume from pushing the node
  into `DiskPressure`, which evicts pods (including OpenStack ones).
- `du -x` on several directories of the same filesystem in one command
  prints nested directories only once; run one `du` per directory.
- `/var/log/pods` is readable only by root (`sudo sh -c` for globs).

**See also**: [Storage](okd-storage.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### Which systemd units matter on the node, and how do I check them?

**Context**: after a reboot, or when the node does not come back
`Ready`.

**How**:

**[READ-ONLY]**

```bash
node 'systemctl is-system-running; systemctl --failed --no-pager'
node 'systemctl list-units --type=service --state=running --no-pager --no-legend | awk "{print \$1}" | tr "\n" " "'
node 'systemd-cgtop -b -n 1 -m --depth=2 | head -8'
node 'systemctl list-timers --no-pager --no-legend | awk "{print \$NF}"'
node 'journalctl -b -p err --no-pager -o cat | cut -c1-80 | sort | uniq -c | sort -rn | head -5; sudo dmesg -T | grep -icE "oom|out of memory"'
```

**Observed on the lab** (2026-11-12):

```text
running
0 loaded units listed.              # nothing failed
auditd chronyd crio dbus-broker dnsmasq fwupd irqbalance kubelet NetworkManager ovs-vswitchd ovsdb-server polkit rhsmcertd rpc-statd rpcbind sshd systemd-journald systemd-logind systemd-udevd ...
kubepods.slice                            4307   24.7G
kubepods.slice/kubepods-burstable.slice   3046   20.4G
kubepods.slice/kubepods-besteffort.slice  1261    4.2G
system.slice                               135    3.9G
system.slice/crio.service                   25    2.8G
system.slice/kubelet.service                53  643.5M
logrotate.timer  systemd-tmpfiles-clean.timer  fstrim.timer  raid-check.timer  ...
0                                   # no OOM kill since boot
```

**Why / how it works**: the boot chain is NetworkManager →
`ovs-configuration.service` (builds `br-ex` on the first NIC) →
`nodeip-configuration.service` (chooses the node IP, writes the kubelet
and CRI-O drop-ins `20-nodenet.conf`) → `crio` → `kubelet` → static
pods → everything else. `dnsmasq` is the single-node local resolver
that answers the cluster's own API and ingress names with the node IP.
Open vSwitch (`ovsdb-server`, `ovs-vswitchd`) runs on the host, not in a
pod, and carries both the cluster network and the OpenStack networks.
There is no automatic operating system updater (`zincati` is absent).
Kolla-Ansible equivalent: `docker.service` and the network scripts; the
rest of that list has no equivalent because Kolla hosts run a general
distribution.

**Pitfalls**:

- `journalctl -b -p err` shows lines from `nodeip-configuration` at
  error priority that are informational (`level=info msg="Writing
  path..."`): the unit logs everything to stderr.
- Restarting `ovs-vswitchd` or NetworkManager on the node interrupts the
  pod network and every OpenStack network attachment at once; not
  tested.
- `systemctl is-system-running` says `running` even when pods crash: it
  only covers host units.

**See also**: [Networking](okd-networking.md),
[Node and OKD troubleshooting](../troubleshooting/node-and-okd.md)

### Is the node clock synchronised, and to what?

**Context**: token validation errors, certificates "not yet valid",
Galera or OVN complaints about time, or simply after a restore from
snapshot.

**How**:

**[READ-ONLY]**

```bash
node 'chronyc -n tracking | head -5; chronyc -n sources; timedatectl | grep -E "synchronized|NTP|Time zone"'
node 'grep -vE "^#|^$" /etc/chrony.conf'
compute 'chronyc -n tracking | grep -E "Reference|System time"'
```

**Observed on the lab** (2026-11-12):

```text
Reference ID    : C0A88205 (192.168.130.5)
Stratum         : 4
System time     : 0.000010512 seconds fast of NTP time
^* 192.168.130.5                 3  10   377   844  +1694us[+1700us] +/-   92ms
^+ <four public pool servers>    2  10   377   ...
System clock synchronized: yes
NTP service: active
Time zone: UTC (UTC, +0000)
pool 0.rhel.pool.ntp.org iburst
server 192.168.130.5 iburst
Reference ID    : C0A88205 (192.168.130.5)        # compute node
System time     : 0.000000093 seconds fast of NTP time
```

The node follows the bastion (192.168.130.5) and also reaches four
servers of a public pool; offset is in microseconds. The compute node
has the bastion as its only source.

**Why / how it works**: `/etc/chrony.conf` is written by the
`50-masters-chrony-configuration` MachineConfig at installation. Pods
have no clock of their own: every OpenStack service uses the node's.
The compute node is configured separately by the data plane (`timesync`
service of the NodeSet). Kolla-Ansible equivalent: the `chrony`
container or host chrony, per node.

**Pitfalls**:

- The file keeps a public `pool` line in addition to the bastion. On a
  network without Internet access the pool is simply unreachable; with
  access, the node may select a public server instead of the bastion. If
  the control plane and the compute node must agree on one source,
  remove the pool line (MachineConfig change, reboot).
- A clock jump of more than the token or certificate tolerance breaks
  authentication cluster-wide; after resuming a suspended lab, check
  `chronyc tracking` before anything else.
- Changing the time source is a MachineConfig change, not an edit of
  `/etc/chrony.conf`.

**See also**: [Infrastructure](../installation/01-infrastructure.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md)

### How long are host logs kept (journal, container logs, audit)?

**Context**: looking for what happened yesterday, or estimating whether
evidence still exists.

**How**:

**[READ-ONLY]**

```bash
node 'journalctl --disk-usage; cat /etc/systemd/journald.conf /etc/systemd/journald.conf.d/* 2>/dev/null | grep -vE "^#|^$"'
node 'journalctl --list-boots --no-pager | head -3; journalctl -k -b -p warning --no-pager | wc -l'
node 'sudo ls -la /var/log/kube-apiserver; sudo du -sh /var/log/kube-apiserver /var/log/oauth-apiserver /var/log/openshift-apiserver /var/log/audit'
oc adm node-logs okd-0 --path=kube-apiserver/ | head
oc get cm -n openshift-kube-apiserver config -o jsonpath='{.data.config\.yaml}' | python3 -c 'import json,sys; d=json.load(sys.stdin)["apiServerArguments"]; [print(k, d[k]) for k in d if "audit-log" in k or "event" in k]'
```

**Observed on the lab** (2026-11-12):

```text
Archived and active journals take up 181.7M in the file system.
[Journal]
Storage=persistent
System Journal (/var/log/journal/<machine id>) is 128M, max 4G, 3.8G free.
17                                  # kernel warnings since boot
-rw-------. 1 root root 209714176 Nov 12 03:21 audit-2026-11-12T03-21-13.628.log
...                                 # one 200 MB file every 55 to 58 minutes
-rw-------. 1 root root 209713642 Nov 12 11:48 audit-2026-11-12T11-48-00.135.log
-rw-------. 1 root root  10614707 Nov 12 11:49 audit.log
2.3G    /var/log/kube-apiserver
13M     /var/log/oauth-apiserver
87M     /var/log/openshift-apiserver
2.8M    /var/log/audit
audit-log-maxbackup ['10']
audit-log-maxsize ['200']
event-ttl ['3h']
```

The journal still holds every boot since the installation (16 hours,
182 MiB); at this rate its 4 GiB cap keeps about two weeks. The API
audit log is very different: ten files of 200 MB, one per hour, so at
11:49 UTC the oldest audit record was from 02:25 UTC. **The audit trail
of this cluster covers about the last ten hours only.**

**Why / how it works**: four independent retention mechanisms exist.
The journal (host units, kubelet, CRI-O, kernel) is persistent with size
limits. Container logs are files rotated by kubelet (50 MiB × 5 per
container) and deleted with the pod. API audit logs are files rotated by
the API server itself. Kubernetes events live in etcd for three hours.
Nothing is shipped off the node: there is no log aggregation in this
lab. Kolla-Ansible equivalent: `/var/log/kolla` with logrotate, and
optionally the central logging stack.

**Pitfalls**:

- The logs of a deleted or replaced pod are gone (except the previous
  container of the same pod, `oc logs --previous`). After an OpenStack
  service rollout, the old pod's logs do not exist any more. Capture
  before restarting.
- A reinstallation of the node erases everything; the journal is not a
  backup of evidence.
- "Who changed this yesterday?" cannot be answered from the audit log:
  it holds about ten hours. If an audit question may come later, copy the
  files off the node the same day (see the access and security file for
  the query). Its 2.3 GiB size is the steady state of the rotation, not
  a leak.
- Events are kept three hours (`event-ttl`): `oc get events` after a
  night shows nothing of the evening.

**See also**: [Logs](../operations/02-logs.md),
[Access and security](okd-access-and-security.md)

### What do cordon, uncordon and drain mean when there is only one node?

**Context**: a maintenance reflex from multi-node clusters ("cordon and
drain before touching the node"), or a node found `SchedulingDisabled`.

**How**:

**[CHANGE]** — cordon only stops new scheduling; running pods are not
touched. Do not run a real drain on this lab.

```bash
oc adm cordon okd-0
oc get node okd-0; oc get node okd-0 -o jsonpath='{.spec}{"\n"}'
oc -n default run kb-cordon-test --image=registry.k8s.io/pause:3.9 --restart=Never
oc -n default get pod kb-cordon-test; oc -n default get events --field-selector involvedObject.name=kb-cordon-test
# what a drain would do, without doing it
oc adm drain okd-0 --dry-run=client --ignore-daemonsets --delete-emptydir-data | awk '{print $1,$2}' | sort | uniq -c
oc adm uncordon okd-0
oc -n default get pod kb-cordon-test; oc -n default delete pod kb-cordon-test
```

**Observed on the lab** (2026-11-12):

```text
node/okd-0 cordoned
okd-0   Ready,SchedulingDisabled   control-plane,master,worker   16h   v1.35.5
{"taints":[{"effect":"NoSchedule","key":"node.kubernetes.io/unschedulable",...}],"unschedulable":true}
kb-cordon-test   0/1   Pending   0   8s
Warning  FailedScheduling  0/1 nodes are available: 1 node(s) were unschedulable. ... Preemption is not helpful for scheduling.
    161 evicting pod                # dry run: 161 pods would be evicted
node/okd-0 uncordoned
kb-cordon-test   1/1   Running      # scheduled within seconds of the uncordon
```

While cordoned, the 20 running OpenStack pods kept running and the APIs
kept answering. The node was back to `Ready` with an empty `spec` after
the uncordon.

**Why / how it works**: cordon sets `spec.unschedulable` and a
`NoSchedule` taint. Existing pods stay; any pod that is recreated while
the node is cordoned (a crash is restarted in place and is not affected,
but a rollout, a job, a CronJob run or a deleted pod is) stays `Pending`
because there is no other node. Drain evicts every pod that is not a
DaemonSet or static pod; on a single node the evicted pods have nowhere
to go and stay `Pending` until the uncordon, so a drain is a full
outage of the OpenStack control plane with no benefit. The machine
config daemon does not even try before a MachineConfig reboot on a
single-node control plane (`Drain not required, skipping`).
Kolla-Ansible equivalent: none on a single controller; on several,
`kolla-ansible stop --limit <host>`.

**Pitfalls**:

- A forgotten cordon is silent: everything works until the next pod
  recreation, then things stay `Pending` with `node(s) were
  unschedulable`. After an interrupted maintenance or a failed
  MachineConfig rollout, check `oc get node` for `SchedulingDisabled`.
- While cordoned, CronJobs (the hourly `keystone-cron` trust flush,
  database backups, `collect-profiles`) create pods that queue as
  `Pending` and all start at the uncordon. Fernet keys are not rotated
  by a CronJob here (see
  [who rotates the Fernet keys](openstack-service-administration.md#who-rotates-the-keystone-fernet-keys)).
- A drain respects PodDisruptionBudgets, but none protects an OpenStack
  pod here and the four platform budgets allow one disruption: a
  server-side dry run showed nothing would block and 198 pods would be
  evicted (see [OKD node maintenance](okd-node-maintenance.md)).
- While cordoned, the `master` MachineConfigPool shows `UPDATING=True`
  and no ready machine, as if a rollout were running.
- To stop the lab, follow the maintenance impact page; cordon and drain
  add nothing to it.

**See also**:
[OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md),
[Workloads and resources](okd-workloads-and-resources.md)

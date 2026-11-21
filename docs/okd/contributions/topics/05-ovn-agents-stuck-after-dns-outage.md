---
title: "05 — OVN agents on the compute node stay disconnected for up to 15 minutes after a control-plane DNS outage"
description: "ovn-controller and the OVN metadata agent on the data plane node reach the southbound database by name (ssl:ovsdbserver-sb.openstack.svc:6642)."
---

# 05 — OVN agents on the compute node stay disconnected for up to 15 minutes after a control-plane DNS outage

- **Target:** `openstack-k8s-operators/edpm-ansible` (the Unbound file
  it already ships for the two agents); the OVN stable branch only as
  a side note
- **Type:** test report, then possibly a one-line configuration change
- **Effort:** small (the lab runs are done; what is left is writing
  the report and comparing it with the tracker ticket)
- **Status:** candidate, lab evidence complete — cause **established**
  on the lab on 2026-11-14 with three provoked DNS outages and a packet
  capture; two candidate settings measured, each with a side effect to
  report
- **Upstream state checked on:** 2026-11-14

## Summary

`ovn-controller` and the OVN metadata agent on the data plane node reach
the southbound database by name
(`ssl:ovsdbserver-sb.openstack.svc:6642`). The name is served by the
`dnsmasq-dns` pod of the control plane, the only nameserver of the node.
When that pod is away for more than about a minute (node reboot,
drain), the agents start failing with
`connect: Address family not supported by protocol` every 8 seconds
and keep failing **after the name resolves again** on the node. They
do reconnect by themselves, but late: on the lab, 15 minutes after the
process had started, nine and a half minutes after the DNS service and
the database were back. A restart of the two services reconnects them
in seconds.

An earlier version of this page said "never reconnect" and "still
stuck after 18 hours". Both statements were wrong: every earlier
occurrence had been repaired by hand after 8 to 15 minutes, and the
"18 hours" was the age of the container, not of the disconnection (see
the corrections below).

The Unbound file that edpm-ansible mounts for both agents
(`cache-max-negative-ttl: 30`) **is** in the lab build and did not
prevent the delay. The delay comes from another libunbound default: a
server that timed out is not asked again until its entry in the
infrastructure cache expires (`infra-host-ttl`, 900 seconds), unless
`infra-keep-probing` is set. A capture on the node shows it: for more
than nine minutes after the DNS service was back, the agents sent
**no** query for the database name while other programs of the node
resolved normally, and they reconnected 904 seconds after the first
failed query. With `infra-keep-probing: yes` or `infra-host-ttl: 60`
in the Unbound file, the same outage ended with a reconnection within
a minute. The useful contribution is that measurement on a
single-nameserver node.

## Why it matters in production

- Any maintenance of the control plane that interrupts its DNS service
  for more than about a minute can leave every compute node cut off
  from the southbound database for up to a quarter of an hour after
  the control plane is healthy again: no new port is wired, no
  security group change is applied, while existing flows keep working.
- The Neutron agent list keeps showing the agents alive as long as no
  northbound change happens, so the usual check lies during that time.
- The `ovn_controller` container is reported `unhealthy` during the
  disconnection and nothing acts on it; the metadata container stays
  `healthy` (see
  [topic 06](06-edpm-agent-healthchecks-not-acted-on.md)).
- During the first minutes `ovn-controller` on OVN 24.03 does not run
  its main loop at all: it is blocked in the name resolution (two
  pauses of about 96 seconds on the lab).
- An operator coming from a deployment where agents use controller IP
  addresses has never met this failure mode, and the natural reaction
  (restart the agents) hides the fact that they recover alone.

## Evidence from the lab

Lab: EDPM node on CentOS Stream 9; in the `ovn_controller` container
the package `ovn24.03-24.03.8-55.el9s` (the binary prints
`ovn-controller 24.03.10-55.el9s`, "Open vSwitch Library 3.3.8") and
`unbound-libs` 1.26.1; the metadata agent uses the Python OVS library
3.3 with `python3-unbound` 1.26.1. One nameserver on the node (the
`dnsmasq-dns` service address). Both containers have
`OVS_UNBOUND_CONF` set and a file that contains only
`cache-max-negative-ttl: 30` (file dated 2026-11-11 on the node). All
times UTC. Evidence directory of the lab: `ovn-stuck/` (files 01 to
11).

### Start of the whole lab, 2026-11-14 (read-only observation)

The compute node and the control-plane node booted at the same time;
nobody touched the agents (`NRestarts=0` for both units at 09:03).

| Time | Event |
| --- | --- |
| 07:38:01-02 | Both agent containers started by systemd, right after `network-online.target`; the DNS service is not reachable yet |
| 07:38:02 to 07:39:38, 07:39:41 to 07:41:17 | `ovn-controller`: two `Unreasonably long ... poll interval` warnings (95983 ms and 96355 ms) |
| 07:39:38 | First `stream_ssl ERR ... connect: Address family not supported by protocol`; then one every 8 s, 96 in total |
| 07:39:41 onwards | Metadata agent: `Unable to open stream to ssl:ovsdbserver-sb.openstack.svc:6642 to retrieve schema: Connection refused`, retried with a growing delay (last ones 07:45:29, 07:48:29, 07:51:29) |
| 07:43:09 | Southbound database pod Ready (container started 07:42:39) |
| 07:43:47 | New `dnsmasq-dns` pod Ready; MetalLB announces the service address |
| 07:53:02 | Last error of `ovn-controller`: 900 s after the container start |
| 07:53:10 | `ovn-controller`: `connected`; container back to `healthy` |
| 07:54:29 | Metadata agent: `connected` on its first retry after 07:53; workers start |

So `ovn-controller` was disconnected for 15 min 08 s after its start,
of which 9 min 23 s with the DNS service and the database available.
During the whole period the log has **no** `failed to resolve` line.

State at 09:03: `connection-status` is `connected`, three established
TCP connections to port 6642, both containers `healthy`. The first
agent list showed the metadata agent `XXX` and the second one, 21
seconds later, showed both alive: the list itself triggers the
counter update that the agent answers (it logged the update at
09:03:15). `tests/smoke-test.sh --functional` then passed (16 checks,
0 failed, 09:03:45 to 09:04:54) with **no restart** of the agents.

### Earlier occurrences, re-read in the journal on 2026-11-14

| Date | What the journal shows | How it ended |
| --- | --- | --- |
| 2026-11-12 00:32 (start of the whole lab) | One 96 s poll warning, a single error at 00:34:12, `connected` at 00:34:13; metadata agent connected at 00:34:22 | Reconnected alone about 100 s after the agents started; the times of the DNS pod for that day were not kept |
| 2026-11-12 19:06 (first MachineConfig roll) | Connected since 01:17:45; `connection closed by peer` at 19:06:51; two 96 s poll warnings; errors every 8 s from 19:08:28 to 19:16:18 | Restarted by hand at 19:16:19, 9 min 28 s after the drop: `connected` within a second |
| 2026-11-12 19:18 (second roll) | `connection closed by peer` at 19:18:35; two 72 s poll warnings; errors from 19:19:48 to 19:26:36 | Restarted by hand at 19:26:38, 8 min 03 s after the drop: `connected` within a second |

The first reboot of the lab (2026-11-11) is no longer in the journal
of the node; the notes of that day say the metadata agent was "still
disconnected fifteen minutes later" before it was restarted.

### Corrections to the earlier version of this page

- "Never recover": not established. No occurrence was left alone for
  more than 15 minutes before 2026-11-14, and on that day both agents
  recovered without help.
- "Stuck after 18 hours": wrong. `ovn_controller Up 18 hours
  (unhealthy)` was read on 2026-11-12 during the first roll, before
  the manual restart of 19:16:19; the journal shows the controller
  connected from 01:17:45 to 19:06:51 that day.
- "The mitigation is not in the lab build": wrong. The file and the
  variable are present in both containers.

### Provoked outages with a capture, 2026-11-14

Method, the same for the three runs: `tcpdump -ni any 'port 53 or
icmp'` on the compute node; the `dnsmasq-dns` deployment of the
control plane scaled to zero through the `OpenStackControlPlane`
(`spec.dns.template.replicas: 0`); 15 seconds later the established
connections of the node to the southbound database closed with
`ss -K`; replica count put back after six minutes; state sampled every
15 seconds (`ovn-appctl connection-status`, established connections to
port 6642, resolution of another service name with `getent` on the
node). The database itself stayed available the whole time. Evidence
directory of the lab: `contrib/05/`.

| | Run 1: file as deployed | Run 2: `infra-keep-probing: yes` added | Run 3: `infra-host-ttl: 60` added |
| --- | --- | --- | --- |
| Agents | running since 07:38 | both restarted 10:59:40 | both restarted 11:08:58 |
| DNS pod removed | 10:38:09 | 11:00:35 | 11:09:53 |
| Connections closed | 10:38:23 | 11:00:50 | 11:10:08 |
| `ovn-controller` blocked poll intervals | 95940 ms, 96285 ms | 73519 ms, 73796 ms, 120059 ms, 120105 ms | one of 312380 ms |
| `Address family not supported` errors | 90, one every 8 s from 10:41:39 to 10:53:19 | 5 | 12, from 11:15:21 to 11:16:15 |
| Node resolves again (`getent`) | 10:44:25 | 11:06:58 | 11:16:12 |
| Queries for the database name after that | none until 10:53:27.68 | 11:07:02, 11:07:36, 11:07:48 | 11:16:23.6 to 11:16:23.8 |
| Metadata agent connected (two processes) | 10:53:27.699, 10:53:28.179 | 11:07:02.651, 11:07:36.542 | 11:16:23.633, 11:16:23.800 |
| `ovn-controller` connected | 10:53:27 | 11:07:48 | 11:16:23 |
| From "node resolves" to all connected | 9 min 03 s | 50 s | 11 s |
| From the connection drop to all connected | 904 s | 418 s | 375 s |

What run 1 establishes:

- Between 10:44:25 and 10:53:27 the capture contains the queries of
  other programs of the node, answered by the new DNS pod every
  minute, and **not one** packet for `ovsdbserver-sb.openstack.svc`,
  while `ovn-controller` logged an error every 8 seconds. The errors
  are answered from the libunbound cache without asking the server.
- The first query for the name leaves at 10:53:27.68, 904 seconds
  after the connections were closed (900 seconds plus the position in
  the 8-second retry cycle), is answered, and the three processes
  connect within half a second.
- The delay is therefore counted from the first failed query of the
  process, not from its start: a long-running agent that loses its
  connection during a DNS outage waits the full 15 minutes.
- The metadata agent behaves the same way with its Python binding: its
  two processes connected in the same second as `ovn-controller`. It
  logs `Connection refused` where `ovn-controller` logs
  `Address family not supported by protocol`.

During the outage itself the queries do not reach the capture: the
service address has no neighbour entry any more and the kernel answers
locally (ICMP host unreachable on the loopback interface). The
conclusion above only uses the period after the DNS service was back.

What runs 2 and 3 show:

- Both settings remove the delay on both agents for a six-minute
  outage.
- With `infra-keep-probing: yes`, `ovn-controller` on OVN 24.03 never
  reaches the fast-failure state: every connection attempt blocks its
  main loop for about 120 seconds for the whole outage, and its
  reconnection is as late as the end of the attempt in progress (50
  seconds here).
- With `infra-host-ttl: 60`, the main loop was blocked once for 312
  seconds, then failed fast for one minute; the name was asked again
  62 seconds after the first fast failure. The wait after the DNS
  service is back is bounded by the configured 60 seconds; 11 seconds
  were observed.

After the runs both files were put back as deployed (same checksum on
both, `cache-max-negative-ttl: 30` only), both services restarted at
11:17:16, `connection-status` `connected`, three established
connections, both containers `healthy`; the capture files were removed
from the node.

**Not verified on the lab:**

- The two settings together, and other values of `infra-host-ttl`.
- Behaviour with more than one nameserver. An open Unbound issue
  (see below) reports that `infra-keep-probing` did not help recovery
  in a setup with several upstream servers.
- An outage shorter than the first blocking call (about 96 seconds)
  and one longer than 15 minutes.
- The start-up case on purpose (agents started while the DNS service
  is down): only observed once, unprovoked, with the deployed file.
- A real reboot of the control-plane node with either setting.
- What makes the blocking calls last 96 s, 72 s, 120 s or 312 s
  depending on the file: the libunbound timeouts that add up to these
  values were not worked out.
- OVN 24.09 or later, where the resolution is asynchronous: the
  blocked main loop should not exist there, the 15-minute silence
  should; neither was run.
- Applying the setting through the edpm-ansible variables and a
  deployment: on the lab the two files were edited on the node.

## What the code says

Read on 2026-11-14.

| Fact | Pointer | Level |
| --- | --- | --- |
| The error text is not about address families: `inet_open_active()` returns `EAFNOSUPPORT` whenever the target could not be turned into an address, which includes "the name did not resolve" | Open vSwitch `lib/socket-util.c`, tag `v3.3.8` (`bc99439446a1c0b94498ad7ea44f3d1d933ead90`); the `ERR` line is printed by `lib/stream-ssl.c` | Established |
| `dns_resolve()` resolves synchronously with `ub_resolve()` unless the program called `dns_resolve_init(true)`; the synchronous path logs nothing on failure | Open vSwitch `lib/dns-resolve.c`, same tag (`dns_resolve`, `dns_resolve_sync__`) | Established |
| `ovn-controller` does not call `dns_resolve_init()` on the 24.03 branch; it does from 24.09 on | OVN `controller/ovn-controller.c` at `v24.03.9` and at `branch-24.03` (`dd45c938817e116e42f9a4f42be4c501d205bf14`): no call; `v24.09.0` and `main` (`3cc2b5bcbd6087fff32d1dc76b1845ab166db31a`): `dns_resolve_init(true)` | Established; explains the blocked main loop and the absence of `failed to resolve` |
| Open vSwitch asks libunbound again at every connection attempt in this path: it keeps no failed state of its own | Open vSwitch `lib/dns-resolve.c`, tag `v3.3.8` | Established |
| libunbound defaults: `infra-host-ttl` 900 s, `infra-keep-probing` off, and the manual says a host marked down "may take infra-host-ttl time to get probed again" | Unbound `util/config_file.c` and `doc/unbound.conf.rst` at `f0653284d69076f22c769170714045019ab4c261` (main, 1.26.3 in development) | Established for that commit |
| The expiry time of an infrastructure cache entry is set when the entry is created, not when the server is marked down; a server above the timeout limit is skipped until then | Unbound `services/cache/infra.c` (`data_entry_init`, `infra_get_lame_rtt`), same commit | Established for that commit |
| The container runs `unbound-libs-1.26.1-1.el9`; the files `services/cache/infra.c` and `services/cache/infra.h` are identical at the tag `release-1.26.1` (`13b6717f1716810523ffb60f971a6c9c5e8ce127`) and at the main commit above; at the tag, `util/config_file.c` sets `host_ttl = 900` (L182), `infra_cache_max_rtt = 120000` (L194), `infra_keep_probing = 0` (L195) and `data_entry_init` sets the expiry to "now plus `host_ttl`" (`infra.c` L528-L532) | Unbound, tag `release-1.26.1`, compared on 2026-11-14 | Established |
| The Unbound file shipped for both agents sets only `cache-max-negative-ttl: 30` | edpm-ansible `roles/edpm_ovn/defaults/main.yml` L67-L76 and `roles/edpm_neutron_metadata/defaults/main.yml` at `3e5e2930038443693cecd21caab5a50db051d93a`; pull requests #1337 and #1338 | Established |
| The units start after `openvswitch.service` only; nothing orders them after name resolution or after the database | edpm-ansible `roles/edpm_ovn/templates/quadlet/ovn_controller.container.j2` L21-L22, same commit; the lab units only add the container shutdown unit | Established |

Put together, the mechanism, **established** by run 1 above: the
agent loses its connection (or starts) while the only nameserver is
unreachable; libunbound times out on it, marks it down in its
infrastructure cache and answers every later request at once with a
failure, without sending a query; the entry expires 900 s after it
was created, the server is asked again, and the next connection
attempt succeeds. A restart recovers at once because a new process
has an empty cache.

## Upstream state

Re-read on 2026-11-14: edpm-ansible `main` is still at
`3e5e2930038443693cecd21caab5a50db051d93a` (2026-11-06); the two
default files are unchanged (variables
`edpm_ovn_controller_unbound_conf_content` in
`roles/edpm_ovn/defaults/main.yml` L67-L76 and
`edpm_neutron_metadata_unbound_conf_content` in
`roles/edpm_neutron_metadata/defaults/main.yml` L28-L37).

Duplicate search on 2026-11-14, issues and pull requests, open and
closed:

| Repository | Query | Result |
| --- | --- | --- |
| `openstack-k8s-operators/edpm-ansible` | `infra-host-ttl`, `infra-keep-probing` | 0 |
| same | `unbound` | 6: pull requests #1337, #1338 and their copies #1343, #1346 (negative TTL file), two unrelated |
| same | `negative ttl` | 2, the same pull requests |
| same | `Address family not supported` | 0 |
| same | `OVS_UNBOUND_CONF` | 2, the same pull requests |
| same | `ovn-controller DNS reconnect` | 2, not about this delay |
| `openstack-k8s-operators/ovn-operator` | `infra-host-ttl`, `infra-keep-probing` | 1, unrelated (#154) |
| `ovn-org/ovn`, `openvswitch/ovs-issues` | `infra-host-ttl`, `infra-keep-probing` | 0 |

Related, in the resolver itself: `NLnetLabs/unbound` issue #1461
"[Infra cache] Upstream servers do not recover after connectivity
loss" (open, 2026-06-15). A maintainer answers there that the
back-off without `infra-keep-probing` is intended; a comment of
2026-10-06 reports the same with forwarders; the reporter says the
option did not help in a setup with several servers. Its pull
request #1241 "Fix infra-keep-probing for low infra-cache-max-rtt
values" was closed in 2025-02. This confirms the behaviour is by design on
the Unbound side and that the place to act is the file shipped by
edpm-ansible.

Not searched: the `ovs-discuss` and `ovs-dev` archives, and Jira
OSPRH-38451 (not readable without an account): its description may
already cover this case.

**Not specific to the lab:** the single nameserver that lives on the
control plane is how the data plane DNS is designed; the lab only makes
the outage longer because the control plane has one node.

## Proposed contribution

1. An issue on edpm-ansible with the three timelines: the shipped
   Unbound file does not cover an unreachable nameserver; on a
   single-nameserver node the agents stay cut off for 15 minutes
   counted from their first failed query.
2. In the same issue, the two measured settings with their side
   effects, and a question rather than a demand: which one, if any,
   would the maintainers take in the two default files? From the lab
   runs, a short `infra-host-ttl` looks like the smaller change for
   `ovn-controller` 24.03 (bounded wait, no 120-second blocking call
   at every attempt); `infra-keep-probing` is the option the Unbound
   manual names for this case. A pull request on the two default
   files only if a maintainer asks for it.
3. Mention, without asking for anything, that `ovn-controller` on the
   24.03 branch resolves synchronously and stops its main loop for
   minutes during the outage. Newer branches do not have this; a
   backport request is the maintainers' call.

Until then the operator can set the two variables named above in the
NodeSet; this was not run on the lab (files edited on the node).

Nothing was posted upstream.

## Reproduction and validation plan

Steps 1 to 6 were executed on 2026-11-14 (results above; step 2
needed no installation, `tcpdump` 4.99.0 is on the node; the outage
lasted six minutes; the connections were closed with `ss -K` because
scaling the DNS service down does not close them). Step 7 was not
executed.

1. `[READ-ONLY]` Record versions and resolver configuration:
   `podman exec ovn_controller ovn-controller --version`,
   `rpm -q unbound-libs` inside the container, `/etc/resolv.conf` of
   the node, the content of the file named by `OVS_UNBOUND_CONF`.
2. `[CHANGE]` Install `tcpdump` on the node if needed, then
   `[READ-ONLY]` capture: `tcpdump -ni any port 53 -w /tmp/dns.pcap`.
3. `[CHANGE]` Scale the DNS service of the control plane to zero for
   five minutes, then bring it back. Note the three times: outage,
   return, and start time of each agent process.
4. `[READ-ONLY]` For 20 minutes, every minute: `ovn-appctl
   connection-status`, last line of both agent logs, number of queries
   for the southbound name in the capture. Expected if the mechanism
   is right: no query between the moment the errors come every 8 s
   and the expiry, then one query and a reconnection. Queries sent
   and answered while the error persists would disprove it.
5. `[CHANGE]` Add `infra-keep-probing: yes` to the two Unbound files
   on the node, restart both services, repeat steps 3 and 4. Expected
   if the setting is enough: reconnection within about two minutes of
   the return of the DNS service. Then the same with
   `infra-host-ttl: 60` instead, to see which one is the smaller
   change.
6. `[CHANGE]` Put the files back as deployed and restart both
   services.
7. Variant to settle the start-up case: reboot the compute node while
   the DNS service is down.

Not planned on the lab: replacing the name by an address in
`ovn-remote`. It would hide the problem, the operator owns that
value, and the address of the database pod is not stable.

## Effort and risk

- Lab part done (three six-minute outages of the lab DNS service).
  What is left is writing; no code.
- Risk of duplicate: medium. The maintainers know the area (they
  merged the negative-TTL file) and the tracker ticket could not be
  read; the value is in the timed single-nameserver data.
- Risk on the settings: both were measured for one outage length, one
  nameserver and OVN 24.03 only. `infra-keep-probing` keeps the main
  loop of `ovn-controller` 24.03 blocked during the outage; a short
  `infra-host-ttl` makes every program using that file ask a dead
  server again every minute. Report both, recommend neither as proven
  for production.

## Review-readiness checklist

- [x] Versions and resolver configuration recorded (2026-11-14)
- [x] Recovery without restart timed once (2026-11-14, start of the
      whole lab)
- [x] Outage reproduced on purpose, with capture (2026-11-14, run 1)
- [x] Same run with `infra-keep-probing: yes`, for both agents
      (2026-11-14, run 2)
- [x] Same run with `infra-host-ttl: 60` (2026-11-14, run 3)
- [x] Installed Unbound version compared with the code read
- [x] Duplicate search repeated with the two setting names
- [ ] Jira OSPRH-38451 read (needs an account) and compared
- [ ] Report adapted to the issue template of the repository by the
      sender

## Open questions

- Answered on 2026-11-14: the capture shows the silence; the Python
  resolver of the metadata agent behaves like the C one; the delay is
  counted from the first failed query.
- Which libunbound timeouts add up to the blocking calls of 96 s,
  120 s and 312 s?
- Which of the two settings do the maintainers prefer, and do they
  want it for both agents?
- What happens with two nameservers of which one is down?

## Draft issue text

> **Title:** ovn-controller and ovn-metadata-agent stay disconnected
> for 15 minutes after a DNS outage on a single-nameserver data plane,
> with the Unbound negative-TTL file in place
>
> **Environment:** EDPM node on CentOS Stream 9; `ovn_controller`
> container with `ovn-controller 24.03.10-55.el9s`, Open vSwitch
> library 3.3.8, `unbound-libs-1.26.1-1.el9`; metadata agent with
> `python3-unbound` 1.26.1; one nameserver on the node (control-plane
> dnsmasq); TLS to the southbound database by name; `OVS_UNBOUND_CONF`
> file with `cache-max-negative-ttl: 30` only (#1337/#1338).
>
> **Reproduction:** capture port 53 on the node, scale the dnsmasq
> deployment to zero, close the node's connections to port 6642, wait
> six minutes, scale back. The database stays available.
>
> **Observed with the shipped file:** `ovn-controller` logs two
> `Unreasonably long ~96000ms poll interval` warnings, then
> `connect: Address family not supported by protocol` every 8 s, 90
> times. The node resolves names again six minutes after the start of
> the outage; the errors continue for nine more minutes. In that
> period the capture shows the queries of other programs being
> answered and no query at all for the database name. The first one
> leaves 904 s after the connection drop and both agents connect in
> the same second. The metadata agent logs `Connection refused`
> during that time.
>
> **Same outage with `infra-keep-probing: yes` added to both files:**
> both agents connected within 50 s of the name resolving again;
> `ovn-controller` logged poll intervals of about 120 s for the whole
> outage (synchronous resolution on 24.03).
>
> **Same outage with `infra-host-ttl: 60` instead:** both agents
> connected 11 s after the name resolved again; one poll interval of
> 312 s, then fast failures for one minute.
>
> **Reading:** libunbound marks the only forwarder as down in its
> infrastructure cache and does not ask it again before
> `infra-host-ttl` (900 s by default, counted from the creation of the
> entry). Checked in the 1.26.1 sources (`services/cache/infra.c`,
> `util/config_file.c`); Unbound issue #1461 describes the same
> back-off as intended.
>
> **Question:** would you take one of these settings in the default
> Unbound file of both roles, and which one? Tested with one outage
> length, one nameserver and OVN 24.03 only.

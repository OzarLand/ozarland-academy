# 05 — OVN agents on the compute node stay disconnected for up to 15 minutes after a control-plane DNS outage

- **Target:** `openstack-k8s-operators/edpm-ansible` (the Unbound file
  it already ships for the two agents); the OVN stable branch only as
  a side note
- **Type:** test report, then possibly a one-line configuration change
- **Effort:** small to medium (one controlled DNS outage with a packet
  capture, one more with a changed Unbound file)
- **Status:** candidate — symptom timed on the lab on 2026-11-14,
  origin of the error message established in the code, the mechanism
  of the delay is **probable, not proven** (no capture, no test of the
  proposed setting)
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
prevent the delay. The delay matches another libunbound default: a
server that timed out is not asked again until its entry in the
infrastructure cache expires (`infra-host-ttl`, 900 seconds), unless
`infra-keep-probing` is set. The useful contribution is a clean
measurement on a single-nameserver node, with a capture, with and
without that setting.

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

**Not verified on the lab:**

- Whether libunbound sends DNS queries while the error repeats: no
  capture was taken. This is the missing proof.
- Whether `infra-keep-probing: yes` or a short `infra-host-ttl`
  removes the delay: not tested.
- What exactly makes the two pauses last 96 s (72 s in one case).
- The time at which the metadata agent created its resolver context;
  its recovery time is only known to the granularity of its retry
  delay (180 s at that point).
- Behaviour with more than one nameserver.
- The libunbound code was read on its main branch, not on the 1.26.1
  tag that the containers run.

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
| The Unbound file shipped for both agents sets only `cache-max-negative-ttl: 30` | edpm-ansible `roles/edpm_ovn/defaults/main.yml` L67-L76 and `roles/edpm_neutron_metadata/defaults/main.yml` at `3e5e2930038443693cecd21caab5a50db051d93a`; pull requests #1337 and #1338 | Established |
| The units start after `openvswitch.service` only; nothing orders them after name resolution or after the database | edpm-ansible `roles/edpm_ovn/templates/quadlet/ovn_controller.container.j2` L21-L22, same commit; the lab units only add the container shutdown unit | Established |

Put together, the **probable** mechanism: the agent starts (or loses
its connection) while the only nameserver is unreachable; libunbound
times out on it, marks it down in its infrastructure cache and
answers every later request at once with a failure, without sending a
query; the entry expires 900 s after it was created, the server is
probed again, and the next connection attempt succeeds. Three
observations fit: the last error 900 s after the process start on
2026-11-14, the change from long blocking calls to immediate failures
every 8 s, and the instant recovery after a restart (a new process
has an empty cache). None of them is a proof.

## Upstream state

Duplicate search on 2026-11-13 (not repeated on 2026-11-14):
edpm-ansible (issues and pull requests, open and closed) for
"unbound", "negative ttl", "Address family not supported": pull
requests #1337 and #1338 and their copies to other branches (#1343
and #1346) only.
`openvswitch/ovs-issues` and `ovn-org/ovn` for "Address family not
supported": nothing relevant. Not searched: "infra-host-ttl" and
"infra-keep-probing" in the same places, the `ovs-discuss` and
`ovs-dev` archives, and Jira OSPRH-38451 (not readable without an
account): its description may already cover this case.

**Not specific to the lab:** the single nameserver that lives on the
control plane is how the data plane DNS is designed; the lab only makes
the outage longer because the control plane has one node.

## Proposed contribution

In this order, and stopping as soon as the question is answered:

1. Reproduce once with a capture and publish the timeline as an issue
   on edpm-ansible: the shipped Unbound file does not cover an
   unreachable nameserver, here is what a single-nameserver node does.
2. If the capture confirms the mechanism and the setting removes the
   delay on both agents: propose it in the same issue, and as a pull
   request on the two default files only if a maintainer asks for it.
3. Mention, without asking for anything, that `ovn-controller` on the
   24.03 branch resolves synchronously and stops its main loop for
   more than three minutes during the outage. Newer branches do not
   have this; a backport request is the maintainers' call.

Nothing was posted upstream.

## Reproduction and validation plan

Not executed; every step below is a plan.

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

- Three short outages of the lab DNS service and about two hours of
  observation; no code.
- Risk of duplicate: medium. The maintainers know the area (they
  merged the negative-TTL file); the value is in the timed
  single-nameserver data.
- Risk of being wrong on the mechanism: real until step 4 is done.
  Report observations and keep the hypothesis clearly marked.
- Risk on the setting: `infra-keep-probing` sends one probe at a time
  to a dead server; harmless with one nameserver, to be confirmed
  with several.

## Review-readiness checklist

- [x] Versions and resolver configuration recorded (2026-11-14)
- [x] Recovery without restart timed once (2026-11-14, start of the
      whole lab)
- [ ] Outage reproduced on purpose, with capture
- [ ] Same run with `infra-keep-probing: yes`, for both agents
- [ ] Jira OSPRH-38451 read (needs an account) and compared
- [ ] Duplicate search repeated with the two setting names
- [ ] Report written from the issue template, hypothesis separated from
      facts

## Open questions

- Does the capture show the silence that the mechanism predicts?
- Does the Python resolver of the metadata agent behave like the C one
  with the same Unbound file? Its recovery on 2026-11-14 is compatible
  with it but only timed to within three minutes.
- Why two pauses of 96 s and then immediate failures: which libunbound
  timeouts add up to that value?
- After a connection drop on a long-running agent, is the delay
  counted from the first failed query (which would make it close to
  15 minutes every time) or can it be shorter?

## Draft issue text

> **Title:** ovn-controller and ovn-metadata-agent stay disconnected
> for up to 15 minutes after a DNS outage on a single-nameserver data
> plane, with the Unbound negative-TTL file in place
>
> **Environment:** (versions from step 1), one nameserver on the EDPM
> node (control-plane dnsmasq), TLS to the southbound database,
> `OVS_UNBOUND_CONF` file with `cache-max-negative-ttl: 30`
> (#1337/#1338).
>
> **Observed:** after N minutes without DNS, `ovn-controller` logs two
> `Unreasonably long ~96000ms poll interval` warnings, then
> `connect: Address family not supported by protocol` every 8 s. The
> errors continue after the name resolves again on the node and stop
> M seconds after (process start / first failed query); it then
> connects at once. The metadata agent follows on its next retry.
> Capture: (queries seen / not seen during the error period).
>
> **With `infra-keep-probing: yes` added to the file:** (result for
> each agent).
>
> **Reading:** libunbound seems to mark the only forwarder as down and
> not probe it again before `infra-host-ttl` (900 s by default).
> (Keep or drop this paragraph depending on the capture.)
>
> **Question:** would you take `infra-keep-probing: yes` (or a short
> `infra-host-ttl`) in the default Unbound file of both roles?

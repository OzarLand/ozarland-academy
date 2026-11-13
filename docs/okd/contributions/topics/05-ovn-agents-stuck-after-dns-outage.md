# 05 — OVN agents on the compute node never reconnect after a control-plane DNS outage

- **Target:** first `openstack-k8s-operators/edpm-ansible` (validation
  of an existing mitigation, then a report if it is not enough); possibly
  Open vSwitch (`ovs-discuss` mailing list) for the root cause
- **Type:** investigation, test report, possibly a bug report
- **Effort:** medium (two controlled outages on the lab, a packet
  capture, careful reading of the resolver code)
- **Status:** candidate — symptom observed three times on the lab; an
  upstream mitigation exists since 2026-10-30 and is **not** in the lab
  build; its explanation does not fully match what the lab logged
- **Upstream state checked on:** 2026-11-13

## Summary

`ovn-controller` and the OVN metadata agent on the data plane node reach
the southbound database by name
(`ssl:ovsdbserver-sb.openstack.svc:6642`). The name is served by the
`dnsmasq-dns` pod of the control plane. When that pod is away for a
while (node reboot, drain), the agents start failing with
`connect: Address family not supported by protocol` every 8 seconds and
**never recover**, although the system resolver of the node answers
again as soon as the pod is back. Only a restart of the two services
fixes it.

Upstream merged a mitigation two weeks before this was written: a
libunbound configuration file with `cache-max-negative-ttl: 30`,
explained by a negative answer being cached for an hour. The lab saw an
agent still stuck after 18 hours, and no "failed to resolve" warning in
the log, which this explanation does not cover. The useful contribution
is a clean test of the mitigation on a single-nameserver deployment,
with a capture, and a precise report if the agents still do not recover.

## Why it matters in production

- Any maintenance of the control plane that interrupts its DNS service
  longer than a reconnection attempt leaves every compute node cut off
  from the southbound database: no new port is wired, no security group
  change is applied, while existing flows keep working. Nothing looks
  broken until a user creates an instance.
- The Neutron agent list keeps showing the agents alive as long as no
  northbound change happens, so the usual check lies.
- The container is reported `unhealthy` and nothing acts on it (see
  [topic 06](06-edpm-agent-healthchecks-not-acted-on.md)).
- An operator coming from a deployment where agents use controller IP
  addresses has never met this failure mode.

## Evidence from the lab

Lab: EDPM node on CentOS Stream 9, OVN package `ovn24.03-24.03.8-55.el9s`
with "Open vSwitch Library 3.3.8", `unbound-libs` 1.26.1, one nameserver
on the node (the `dnsmasq-dns` service).

- Evidence file `kb4/16-ovn-compute.txt` of the lab (2026-11-12):
  `stream_ssl|ERR|ssl:ovsdbserver-sb.openstack.svc:6642: connect: Address family not supported by protocol`
  every 8 s, log sequence numbers consecutive from 553 to 577 with no
  other message in between, while `getent hosts` on the node returned
  the right address.
- Container state at the same time: `ovn_controller Up 18 hours
  (unhealthy)` after the first control-plane restart, and
  `ovn_metadata_agent ... (healthy)` while its connection was down.
- Restart of both services: `connected` in less than 10 s.
- Recorded in
  [the knowledge base](../../docs/knowledge-base/okd-node-maintenance.md#why-are-the-ovn-agents-of-the-compute-node-dead-after-a-reboot-of-the-okd-node-and-how-do-i-fix-them),
  seen on three control-plane restarts; on the first one only the
  metadata agent was stuck.

**Not verified on the lab:**

- Whether the stuck process still sends DNS queries (no capture taken).
- Whether the mitigation file fixes it: the lab collection predates it.
- The exact Open vSwitch commit inside the container image; "3.3.8" is
  what the binary prints.
- Behaviour with more than one nameserver.

## Upstream state

Looked at on 2026-11-13. edpm-ansible `main` at
`3e5e2930038443693cecd21caab5a50db051d93a`; Open vSwitch `main` at
`779c08f1436ae6df90276b8c3027ebd79282d00c`.

| Fact | Pointer |
| --- | --- |
| Mitigation: Unbound file with `cache-max-negative-ttl: 30`, selected with `OVS_UNBOUND_CONF` | edpm-ansible [`roles/edpm_ovn/defaults/main.yml` L67-L76](https://github.com/openstack-k8s-operators/edpm-ansible/blob/3e5e2930038443693cecd21caab5a50db051d93a/roles/edpm_ovn/defaults/main.yml#L67-L76); pull request #1337 (`main`, merged 2026-10-30) and #1338 (`18-stable`), Jira OSPRH-38451 |
| A request in state "pending" is not retried; only a finished request is | ovs [`lib/dns-resolve.c` L174](https://github.com/openvswitch/ovs/blob/779c08f1436ae6df90276b8c3027ebd79282d00c/lib/dns-resolve.c#L174) |
| A failure of `ub_resolve_async` sets the error state without a log line; the warning "failed to resolve" is only in the callback | same file, L261-L268 and L283-L284 |
| The connection error text comes from the address parser failing on a name without address | ovs `lib/socket-util.c` L563-L564 (returns `EAFNOSUPPORT`) |
| Earlier upstream fix in the same area, already in 3.3.8: "dns-resolve: Do not treat never accessed responses as expired" | ovs commit `0b29edb5cbdcffc60e29b2613aa375c39bbaa8c1` (2025-11-14); on `branch-3.3` as `7e1e83718e`. Its message says a proper fix needs the reconnect logic to know about DNS |
| The Python resolver used by the metadata agent has the same logic | ovs `python/ovs/dns_resolve.py` |

Duplicate search on 2026-11-13: edpm-ansible (issues and pull requests,
open and closed) for "unbound", "negative ttl", "Address family not
supported": #1337, #1338 and their copies to other
branches (#1343, #1346) only. `openvswitch/ovs-issues` and `ovn-org/ovn`
for "Address family not supported": nothing relevant. The mailing list
archives of `ovs-discuss` and `ovs-dev` were **not** searched
systematically, and Jira OSPRH-38451 could not be read: its description
may already cover the lab's case.

**Not specific to the lab:** the single nameserver that lives on the
control plane is how the data plane DNS is designed; the lab only makes
the outage longer because the control plane has one node.

## Proposed contribution

In this order, and stopping as soon as the question is answered:

1. Validate the upstream mitigation on a single-nameserver deployment and
   publish the result where the maintainers will see it (a comment-free
   issue of our own on edpm-ansible, with logs and capture). A
   confirmation with data is a contribution in itself.
2. If the agents still do not recover: bug report on edpm-ansible, with
   the state of the resolver (pending or error) deduced from the capture
   and the log.
3. Only if the root cause is shown to be in Open vSwitch: a message to
   `ovs-discuss` with the same data. A patch to the reconnect logic is
   not a first contribution; do not attempt it without a maintainer's
   lead.

## Reproduction and validation plan

1. `[READ-ONLY]` Record versions: `podman exec ovn_controller ovn-controller --version`,
   `rpm -q unbound-libs` inside the container, `/etc/resolv.conf` of the
   node, `podman exec ovn_controller env | grep UNBOUND`.
2. `[READ-ONLY]` Start a capture on the node:
   `tcpdump -ni any port 53 -w /tmp/dns.pcap`.
3. `[CHANGE]` Scale the DNS service of the control plane to zero for
   five minutes (or reboot the control-plane node), then bring it back.
4. `[READ-ONLY]` For 70 minutes (longer than the default negative cache
   of 3600 s), every few minutes: `ovn-appctl connection-status`, last
   lines of the controller log, number of DNS queries for the southbound
   name in the capture. Queries present and answered while the error
   persists point at the cache; no query at all points at a request that
   is never retried.
5. `[CHANGE]` Restart both services, note the recovery time.
6. `[CHANGE]` Deploy the collection that contains #1338 (or mount the
   same Unbound file by hand on a test node), repeat steps 2 to 4.
   Expected if the mitigation is enough: recovery within about 30 s of
   DNS coming back.
7. Repeat step 6 for the metadata agent: the same pull requests mount
   the file and set `OVS_UNBOUND_CONF` for it too
   (`roles/edpm_neutron_metadata/templates/quadlet/ovn_metadata_agent.container.j2`
   L40-L42), but its resolver is the Python one.

## Effort and risk

- Two outages of the lab control plane and about three hours of
  observation; no code.
- Risk of duplicate: medium. The maintainers know the area (they merged
  the mitigation); the value is in the single-nameserver data and in the
  18-hour case, not in announcing the problem.
- Risk of being wrong on the root cause: real. Report observations and
  keep the hypothesis clearly marked.

## Review-readiness checklist

- [ ] Versions and resolver configuration recorded (step 1)
- [ ] Outage reproduced without the mitigation, with capture
- [ ] Same run with the mitigation, for both agents
- [ ] Jira OSPRH-38451 read (needs an account) and compared
- [ ] `ovs-discuss` archive searched for the error text
- [ ] Report written from the issue template, hypothesis separated from
      facts

## Open questions

- Is the request stuck in "pending" because the only nameserver was
  unreachable when the query was sent, or is it a silent error from
  `ub_resolve_async`?
- Does the Python resolver of the metadata agent behave like the C one
  with the same Unbound file?
- Why did `ovn-controller` reconnect alone on the first restart of the
  lab and not on the next two? Duration of the outage is the first
  suspect.

## Draft issue text

> **Title:** ovn-controller and ovn-metadata-agent stay disconnected
> after a DNS outage on a single-nameserver data plane: test results
> with and without the Unbound negative TTL setting
>
> **Environment:** (versions from step 1), one nameserver on the EDPM
> node (control-plane dnsmasq), TLS to the southbound database.
>
> **Without the setting:** after N minutes without DNS, both agents log
> `connect: Address family not supported by protocol` every 8 s and do
> not recover in M hours although `getent hosts` answers. Capture:
> (queries seen / not seen).
>
> **With `cache-max-negative-ttl: 30` (#1337/#1338):** (result for each
> agent).
>
> **Question:** (only if it still fails) the log shows no "failed to
> resolve" warning during the whole period, which suggests the request
> never completes rather than a cached negative answer. Is this known?

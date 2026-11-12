# OpenStack networking with OVN

> Status: every command was run on the lab (OKD 4.22, operators 18-stable,
> OpenStack 2023.1 Antelope, OVN 24.03, one KVM compute node) on 2026-11-12

Neutron uses the ML2/OVN driver. The OVN databases and `ovn-northd` are
pods; `ovn-controller`, the metadata agent and Open vSwitch run on the
compute node. Commands run on the bastion in the `openstack` namespace
unless stated otherwise. `os` is the admin client, `$o` the member client
(see [identity and tenants](openstack-identity-and-tenants.md)):

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
export OS_CLIENT_CONFIG_FILE=~/kb-demo/clouds.yaml OS_CLOUD=kb-demo
o=~/kb-demo/venv/bin/openstack
compute() { ssh -i ~/okd-openstack-lab/.work/dataplane-ssh-key cloud-admin@192.168.122.100 "$@"; }
```

## Entries

### How do I create the external provider network for floating IPs?

**Context**: instances need a way out and floating IPs need a pool. On the
lab the physical network `datacentre` is the control-plane network
192.168.122.0/24, and the range .150 to .199 is reserved for floating IPs.

**How**:

**[READ-ONLY]**

```bash
os network agent list
compute sudo ovs-vsctl get open_vswitch . external_ids:ovn-bridge-mappings
```

**[CHANGE]** Admin only: an external network must name a physical network.

```bash
os network create kb-public --external --provider-network-type flat \
  --provider-physical-network datacentre
os subnet create kb-public-subnet --network kb-public --subnet-range 192.168.122.0/24 \
  --gateway 192.168.122.1 --allocation-pool start=192.168.122.150,end=192.168.122.199 --no-dhcp
```

**Observed on the lab** (2026-11-12):

```text
| OVN Metadata agent           | edpm-compute-0.ctlplane.okd.lab.example.com | :-)   | UP    |
| OVN Controller Gateway agent | edpm-compute-0.ctlplane.okd.lab.example.com | :-)   | UP    |
"datacentre:br-ex"
mtu: 1442
provider:network_type: flat
provider:physical_network: datacentre
router:external: true
```

**Why / how it works**: the NodeSet variable `edpm_ovn_bridge_mappings`
maps `datacentre` to the bridge `br-ex`, which holds the first interface
of the compute node. Neutron writes a `localnet` port in OVN and
`ovn-controller` patches `br-int` to `br-ex`. Kolla-Ansible equivalent:
`neutron_external_interface` and `physnet1` on `br-ex`.

**Pitfalls**:

- The name must be `datacentre` (British spelling); any other physical
  network name is accepted by the API but no chassis maps it, so ports
  never get bound.
- Keep the allocation pool inside .150 to .199: lower addresses belong to
  the node, the load-balancer pool and the DNS service.
- The MTU of this "physical" network is 1442, not 1500, because the lab
  itself runs inside an overlay. It comes from `global_physnet_mtu` in the
  control plane resource.
- Use `--no-dhcp`: OVN would otherwise answer DHCP on the control-plane
  network.

**See also**: [Architecture](../architecture.md),
[OpenStack data plane](../installation/06-openstack-data-plane.md),
[Network troubleshooting](../troubleshooting/network.md)

### How does a project build its network, router and floating IP?

**Context**: self-service part, done by a project member with no admin
right.

**How**:

**[CHANGE]**

```bash
$o network create kb-demo-net
$o subnet create kb-demo-subnet --network kb-demo-net --subnet-range 10.20.0.0/24 \
  --dns-nameserver 192.168.122.80
$o router create kb-demo-router
$o router set kb-demo-router --external-gateway kb-public
$o router add subnet kb-demo-router kb-demo-subnet
$o floating ip create kb-public -f value -c floating_ip_address
$o server add floating ip kb-vm1 192.168.122.159
```

**[READ-ONLY]**

```bash
os network show kb-demo-net -f yaml | grep -E 'mtu|provider'
$o router show kb-demo-router -f yaml | grep -A6 external_gateway_info
```

**Observed on the lab** (2026-11-12):

```text
mtu: 1384
provider:network_type: geneve
provider:physical_network: null
provider:segmentation_id: 37789
  enable_snat: true
  - ip_address: 192.168.122.184
```

The router took the first free address of the pool for source NAT, the
floating IP another one.

**Why / how it works**: tenant networks are Geneve overlays between
chassis (`tenant_network_types = geneve`); routers and NAT are logical
objects in OVN, not namespaces. The MTU is the physical MTU minus the
Geneve overhead (1442 - 58). Kolla-Ansible equivalent: the same commands;
with ML2/OVS you would look for `qrouter-` namespaces, which do not exist
here.

**Pitfalls**:

- A member sees `provider:network_type: null`; only an admin sees the
  segment.
- 192.168.122.80 is the lab DNS service. Without `--dns-nameserver`,
  instances get no resolver.
- The router gateway and every floating IP consume addresses of the
  50-address pool, and each counts against the project quota.

**See also**: [Architecture](../architecture.md),
[DNS and routing](../troubleshooting/dns-and-routing.md)

### How do I check connectivity, MTU, DNS and metadata from inside an instance?

**Context**: "my instance has no network" is the most common ticket. Check
from both sides before opening OVN.

**How**:

**[READ-ONLY]** From the bastion, then inside the instance (CirrOS user
`cirros`).

```bash
ip route get 192.168.122.159
ping -c 3 192.168.122.159
ssh -i ~/kb-demo/id_kb cirros@192.168.122.159
# inside the instance:
ip link show eth0
ip route
cat /etc/resolv.conf
ping -c2 -W2 10.20.0.30
ping -c2 -W2 192.168.122.1
ping -c2 -s 1356 -M do 10.20.0.30
ping -c2 -s 1357 -M do 10.20.0.30
curl -s -m 5 http://169.254.169.254/latest/meta-data/instance-id
curl -s -m 5 http://169.254.169.254/latest/meta-data/public-ipv4
nslookup kb-vm2
```

**Observed on the lab** (2026-11-12): ping and SSH to the floating IP
worked at the first try (1.7 ms average) right after the second
instance became active.

```text
192.168.122.159 via 192.168.130.1 dev eth0 src 192.168.130.5
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1384 qdisc pfifo_fast qlen 1000
default via 10.20.0.1 dev eth0  src 10.20.0.54  metric 1002
169.254.169.254 via 10.20.0.2 dev eth0  src 10.20.0.54  metric 1002
domain openstackgate.local
nameserver 192.168.122.80
i-0000000d
192.168.122.159
```

A 1356-byte payload passes with "do not fragment", 1357 does not: the MTU
of 1384 is real. `kb-vm2` and `kb-vm2.openstackgate.local` resolve to
10.20.0.30, and so do external names. A ping to the DNS address
192.168.122.80 fails although DNS answers.

**Why / how it works**: OVN answers DHCP itself (no dnsmasq, no agent) and
hands out the MTU, the resolver and a host route sending 169.254.169.254
to the metadata port (10.20.0.2). OVN also answers DNS queries for the
names of the ports of the network; everything else goes to the configured
resolver. Kolla-Ansible equivalent: `neutron_dhcp_agent` and
`qdhcp-` namespaces with ML2/OVS.

**Pitfalls**:

- The bastion reaches the floating IP **through the lab router**
  (192.168.130.1), not directly. A missing route there looks like a broken
  floating IP.
- The DNS address is a load-balancer virtual IP that only forwards
  port 53: no ping reply is normal.
- BusyBox `nslookup` prints "No answer" for the IPv6 lookup even when the
  IPv4 answer is there; read the whole output.
- Instances have no direct Internet access on the lab (proxy only): a
  failing `curl` to the outside is not a Neutron fault.

**See also**: [Network troubleshooting](../troubleshooting/network.md),
[DNS and routing](../troubleshooting/dns-and-routing.md)

### How do I run ovn-nbctl, ovn-sbctl and ovn-trace on this platform?

**Context**: in Kolla-Ansible you `docker exec ovn_nb_db ovn-nbctl ...`.
Here the databases are pods with TLS listeners; you need the right pod,
container and socket.

**How**:

**[READ-ONLY]**

```bash
oc get pods -l service=ovsdbserver-nb -o jsonpath='{.items[0].spec.containers[*].name}{"\n"}'
oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovn-nbctl show
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-sbctl show
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-sbctl lflow-list | wc -l
oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovs-appctl -t /etc/ovn/ovnnb_db.ctl cluster/status OVN_Northbound
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovs-appctl -t /etc/ovn/ovnsb_db.ctl cluster/status OVN_Southbound
oc exec ovn-northd-0 -c ovn-northd -- ovn-appctl -t /tmp/ovn-northd.1.ctl status
oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovn-nbctl get NB_Global . nb_cfg sb_cfg hv_cfg
```

**Observed on the lab** (2026-11-12):

```text
ovsdbserver-nb openstack-network-exporter
Role: leader
Status: active
64
64
64
```

No option is needed: inside the database pods the tools use the local
unix socket (`/etc/ovn/ovnnb_db.sock`, `/etc/ovn/ovnsb_db.sock`). Remote
clients (Neutron, `ovn-controller`) use
`ssl:ovsdbserver-nb.openstack.svc:6641` and
`ssl:ovsdbserver-sb.openstack.svc:6642` with the certificates
`/etc/pki/tls/certs/ovndb.crt`, `/etc/pki/tls/private/ovndb.key` and the
CA `/etc/pki/tls/certs/ovndbca.crt`. `lflow-list` printed 394 lines for
two networks, one router and two instances, 302 once the instances were
deleted.

**Why / how it works**: the OVN operator runs each database as a
one-member RAFT cluster in a StatefulSet with a persistent volume, and
sets `OVN_RUNDIR=/etc/ovn` so that sockets live next to the data.
Kolla-Ansible equivalent: `docker exec ovn_nb_db ovn-nbctl show` on a
controller.

**Pitfalls**:

- `ovn-appctl -t ovn-northd status` fails (no pid file); the control
  socket is `/tmp/ovn-northd.1.ctl`.
- The Neutron pod has `ovsdb-client` and the certificates but **no**
  `ovn-nbctl`; do not look for the tools there.
- Each OVN pod has a second container, `openstack-network-exporter`:
  always pass `-c`.
- `nb_cfg`, `sb_cfg` and `hv_cfg` must be equal. If `hv_cfg` lags, a
  chassis is not applying changes.
- Read-only here means read-only by discipline: the same tools can delete
  logical objects that Neutron will not recreate by itself.

**See also**: [Network troubleshooting](../troubleshooting/network.md),
[Inspect service status](../operations/01-inspect-service-status.md),
[Control plane and data plane](../concepts/06-control-plane-and-data-plane.md)

### What do the OVN northbound and southbound databases show for a project network?

**Context**: you want to confirm that what Neutron shows really exists in
OVN: switch, ports, router, NAT, security groups, DHCP.

**How**:

**[READ-ONLY]**

```bash
nb() { oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovn-nbctl "$@"; }
sb() { oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-sbctl "$@"; }
nb show
nb lr-nat-list neutron-<router-id>
nb lr-route-list neutron-<router-id>
nb list DHCP_Options
nb list Port_Group
nb acl-list pg_<security-group-id-with-underscores>
sb show
sb list Port_Binding
```

**Observed on the lab** (2026-11-12), identifiers shortened:

```text
switch <uuid> (neutron-<network-id>) (aka kb-demo-net)
    port <port-id>
        addresses: ["<mac> 10.20.0.54"]
    port <port-id>
        type: localport
        addresses: ["<mac> 10.20.0.2"]
    port <port-id>
        type: router
        router-port: lrp-<port-id>
router <uuid> (neutron-<router-id>) (aka kb-demo-router)
    port lrp-<port-id>
        networks: ["192.168.122.184/24"]
        gateway chassis: [<chassis-id>]
    nat <uuid>
        external ip: "192.168.122.159"
        logical ip: "10.20.0.54"
        type: "dnat_and_snat"
    nat <uuid>
        external ip: "192.168.122.184"
        logical ip: "10.20.0.0/24"
        type: "snat"
```

The external switch has a `localnet` port named `provnet-<id>`. DHCP
options carry `mtu=1384`, the resolver, a 12-hour lease and the classless
route to the metadata address. Security groups are port groups
`pg_<id>` with ACLs at priority 1002 (allow-related); the group
`neutron_pg_drop` drops the rest at priority 1001.

**Why / how it works**: Neutron translates every API object into
northbound rows named after the Neutron ID (`neutron-<id>`), `ovn-northd`
compiles them into logical flows in the southbound database, and each
`ovn-controller` turns those into OpenFlow. Kolla-Ansible equivalent: the
same databases; with ML2/OVS the equivalent information is spread over
agents, namespaces and iptables.

**Pitfalls**:

- The `localport` in every network is the metadata port. It is not a
  fault and not a stale DHCP port.
- The floating IP row has `external_mac` and `logical_port` set: NAT is
  done on the chassis that hosts the instance (distributed), not on the
  gateway chassis.
- Port group names replace `-` with `_` in the security group ID.
- `ovn-nbctl acl-list` needs a switch or port group name; with an empty
  argument it fails.

**See also**: [Network troubleshooting](../troubleshooting/network.md),
[Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md)

### How do I trace a packet through OVN without sending it?

**Context**: an instance cannot reach another one or the outside, and you
want to know which logical stage drops the packet.

**How**:

**[READ-ONLY]** Collect the logical switch name, the port IDs and MAC
addresses first.

```bash
os port list --network kb-demo-net -c ID -c "MAC Address" -c "Fixed IP Addresses"
LS=neutron-$(os network show kb-demo-net -f value -c id)
```

**[READ-ONLY]** East-west, then north-south through the router.

```bash
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-trace --summary "$LS" \
  "inport == \"$P1\" && eth.src == $M1 && eth.dst == $M2 && ip4.src == 10.20.0.54 && ip4.dst == 10.20.0.30 && icmp4.type == 8 && ip.ttl == 64"
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-trace --minimal "$LS" \
  "inport == \"$P2\" && eth.src == $M2 && eth.dst == $RM && ip4.src == 10.20.0.30 && ip4.dst == 192.168.122.1 && icmp4.type == 8 && ip.ttl == 64"
```

`P1`/`M1` and `P2`/`M2` are the port ID and MAC of the two instances, `RM`
the MAC of the router port 10.20.0.1.

**Observed on the lab** (2026-11-12):

```text
ingress(dp="kb-demo-net", inport="<port-1>") {
    reg0[15] = check_in_port_sec();
    ...
    outport = "<port-2>";
    output;
    egress(dp="kb-demo-net", inport="<port-1>", outport="<port-2>") {
        ...
        /* output to "<port-2>", type "" */;
```

```text
ct_next(ct_state=est|trk /* default (use --ct to customize) */) {
    ip.ttl--;
    ct_next(ct_state=est|trk /* default (use --ct to customize) */) {
        ct_snat(ip4.src=192.168.122.184) {
            output("provnet-<id>");
```

**Why / how it works**: `ovn-trace` evaluates the logical flows of the
southbound database against a described packet. It proves the logical
configuration (port security, ACLs, routing, NAT) without touching the
data path. Kolla-Ansible equivalent: `docker exec ovn_sb_db ovn-trace`.

**Pitfalls**:

- A good trace proves the **logical** path only. If it ends in `output`
  and the packet is still lost, look at the chassis (OpenFlow, tunnels,
  bridge mapping).
- Connection tracking is simulated: by default every packet is treated as
  established. Add `--ct new` to test whether a security group lets a
  **new** connection in.
- Use `--detailed` to see the table and rule that drops; `--summary` hides
  them.
- The destination MAC must be the router port for routed traffic, not the
  final host.

**See also**: [Network troubleshooting](../troubleshooting/network.md)

### How do I check whether a security group lets a new connection in?

**Context**: "port 80 does not answer". Is it the security group or the
guest? The default trace treats packets as part of an established
connection and therefore proves nothing about the rules.

**How**:

**[READ-ONLY]** Same variables as in the previous entry: `P2`/`M2` for
the source instance, `M1` and the address of the target.

```bash
for port in 22 80; do
  oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-trace --ct new --minimal "$LS" \
    "inport == \"$P2\" && eth.src == $M2 && eth.dst == $M1 && ip4.src == 10.20.0.127 && ip4.dst == 10.20.0.121 && ip.ttl == 64 && tcp.dst == $port && tcp.src == 40000"
done
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-trace --ct new --detailed "$LS" \
  "inport == \"$P2\" && eth.src == $M2 && eth.dst == $M1 && ip4.src == 10.20.0.127 && ip4.dst == 10.20.0.121 && ip.ttl == 64 && tcp.dst == 80 && tcp.src == 40000" | grep -E 'acl'
$o security group rule list kb-demo-ssh -c "IP Protocol" -c "Port Range" -c Direction -c "IP Range"
```

**Observed on the lab** (2026-11-12), security group with ICMP and TCP 22
allowed in:

```text
# tcp 22
ct_next(ct_state=new|trk) {
    ct_next(ct_state=est|trk /* default (use --ct to customize) */) {
        output("<port>");
    };
};
# tcp 80
ct_next(ct_state=new|trk) {
    ct_next(ct_state=est|trk /* default (use --ct to customize) */);
};
 4. ls_out_acl_eval (northd.c:6836): reg0[10] == 1 && (outport == @neutron_pg_drop && ip), priority 2001
```

Port 22 ends in `output` to the target port. Port 80 ends with no output:
the detailed trace shows the packet matching the `neutron_pg_drop` port
group in the **egress pipeline of the switch**, which is the ingress
direction of the target instance.

**Why / how it works**: every port with port security belongs to the
port group `neutron_pg_drop`, whose ACLs drop all IP traffic at priority
2001; each security group rule is an `allow-related` ACL at priority
2002 on the group `pg_<security-group-id>`. `--ct new` tells the trace
that the first conntrack lookup finds no connection. Kolla-Ansible
equivalent: same with ML2/OVN; with ML2/OVS you would read iptables or
OpenFlow firewall rules on the compute node.

**Pitfalls**:

- Without `--ct new` both traces end in `output`: the default assumes an
  established connection, which security groups always allow.
- "Ingress" for Neutron is the `ls_out_*` stages for OVN (out of the
  switch, towards the instance). Do not look for the drop in `ls_in_*`.
- Traffic between two instances also passes the **egress** rules of the
  source; the group has the two default rules that allow all egress.
- A trace that ends in `output` while the service still does not answer
  points to the guest (firewall, service not listening).

**See also**: [Network troubleshooting](../troubleshooting/network.md),
[identity and tenants](openstack-identity-and-tenants.md)

### Which chassis is the gateway and how is it scheduled?

**Context**: north-south traffic of instances without a floating IP leaves
through a gateway chassis. On a real cloud you choose which nodes may take
that role.

**How**:

**[READ-ONLY]**

```bash
sb() { oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-sbctl "$@"; }
nb() { oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovn-nbctl "$@"; }
sb list Chassis
sb find Port_Binding type=chassisredirect
nb list Gateway_Chassis
oc get openstackdataplanenodeset openstack-edpm -o jsonpath='{.spec.nodeTemplate.ansible.ansibleVars.edpm_enable_chassis_gw}{"\n"}'
compute sudo ovs-vsctl get open_vswitch . external_ids:ovn-cms-options
```

**Observed on the lab** (2026-11-12):

```text
hostname            : edpm-compute-0.ctlplane.okd.lab.example.com
logical_port        : cr-lrp-<port-id>
priority            : 1
true
enable-chassis-as-gw
```

The router's external port shows `status: {hosting-chassis="<chassis-id>"}`
and the `cr-lrp-` port is bound to the only chassis.

**Why / how it works**: `edpm_enable_chassis_gw: true` in the NodeSet makes
the `ovn` data plane service write `ovn-cms-options=enable-chassis-as-gw`
in Open vSwitch; Neutron then schedules each router gateway port on up to
five such chassis with priorities, and OVN moves the port to the next one
when the first fails. Kolla-Ansible equivalent: hosts of the `network`
group get the same option (`neutron_ovn_distributed_fip` decides about
floating IPs).

**Pitfalls**:

- With one chassis there is one candidate at priority 1 and **no
  failover**: stopping `ovn_controller` on the compute node cuts all
  routed traffic.
- If no chassis carries the option, routers are created but the gateway
  port stays unbound and nothing tells you in the API.
- Changing the variable needs a new data plane deployment that runs the
  `ovn` service; editing Open vSwitch by hand is reverted at the next run.

**See also**: [Data plane changes](../operations/08-dataplane-changes.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md),
[Control plane and data plane](../concepts/06-control-plane-and-data-plane.md)

### What does the compute node look like from the Open vSwitch side?

**Context**: the logical configuration is right but traffic does not flow.
The next stop is the node.

**How**:

**[READ-ONLY]**

```bash
compute 'sudo podman ps --format "{{.Names}} {{.Status}}"'
compute 'systemctl list-units --type=service --no-pager | grep edpm'
compute sudo ovs-vsctl show
compute sudo ovs-vsctl --columns=external_ids list open_vswitch .
compute sudo podman exec ovn_controller ovn-appctl -t ovn-controller connection-status
compute 'sudo ovs-ofctl dump-flows br-int | wc -l'
compute sudo ovs-ofctl dump-flows br-ex
```

**Observed on the lab** (2026-11-12), two instances running:

```text
ovn_controller Up 6 hours (healthy)
ovn_metadata_agent Up 6 hours (healthy)
nova_compute Up 2 minutes
neutron-haproxy-ovnmeta-<network-id> Up 12 minutes
connected
743
 cookie=0x0, duration=..., table=0, n_packets=..., priority=0 actions=NORMAL
```

`br-int` (fail mode `secure`) holds one `tap` port per instance, one for
the metadata namespace and a patch port to `br-ex`. `br-ex` holds the
first network interface and the node address 192.168.122.100, with a
single `NORMAL` flow. The 743 flows of `br-int` are spread over tables 0
to 85. Open vSwitch (3.3) runs on the host; `ovn-controller` is a
container managed by the systemd unit `edpm_ovn_controller`.

**Why / how it works**: `ovn-controller` connects to the southbound
database (`external_ids:ovn-remote = ssl:ovsdbserver-sb.openstack.svc:6642`),
claims the ports whose `iface-id` it finds on `br-int` and programs
OpenFlow. The tunnel endpoint is `ovn-encap-ip` (172.19.0.100, tenant
network). Kolla-Ansible equivalent: containers `openvswitch_vswitchd`,
`openvswitch_db` and `ovn_controller`; here only the last one is a
container.

**Pitfalls**:

- With a single chassis there is **no Geneve port** on `br-int`: nothing
  to tunnel to. Do not take its absence for a fault on the lab.
- `br-ex` carries the node's own management address. A mistake on that
  bridge cuts SSH and the link to the control plane at once.
- `ovs-vsctl` works on the host directly; `ovn-appctl` must run inside the
  `ovn_controller` container.
- Restarting `edpm_ovn_controller` is not harmless on a single gateway
  chassis (see the gateway entry above).

**See also**: [Data plane troubleshooting](../troubleshooting/dataplane.md),
[Network troubleshooting](../troubleshooting/network.md),
[OpenStack data plane](../installation/06-openstack-data-plane.md)

### How does the metadata service reach an instance?

**Context**: cloud-init hangs or the SSH key is not injected: the instance
cannot reach 169.254.169.254.

**How**:

**[READ-ONLY]**

```bash
compute ip netns list
compute 'sudo ip netns exec ovnmeta-<network-id> ip -br addr'
compute 'sudo ip netns exec ovnmeta-<network-id> ss -ltnp'
compute 'sudo podman ps --format "{{.Names}}" | grep haproxy'
compute 'sudo cat /var/lib/neutron/ovn-metadata-proxy/<network-id>.conf'
compute 'sudo podman logs --since 10m ovn_metadata_agent 2>&1 | grep "GET /latest"'
oc get pods -l service=nova-metadata
```

**Observed on the lab** (2026-11-12): one namespace `ovnmeta-<network-id>`
per network with instances on the node; its interface holds
`169.254.169.254/32` and `10.20.0.2/24`. A container
`neutron-haproxy-ovnmeta-<network-id>` listens on 169.254.169.254:80,
adds the header `X-OVN-Network-ID` and forwards to the unix socket
`/var/lib/neutron/metadata_proxy` of the agent. Each request of the
instance appears in the agent log. After the last instance of the network
was deleted, the namespace and the haproxy container were gone.

**Why / how it works**: the `localport` of the network is plugged in the
namespace; haproxy hands the request to `ovn_metadata_agent`, which signs
it and calls the `nova-metadata` pod over the internal API network.
Kolla-Ansible equivalent: `neutron_ovn_metadata_agent`, where haproxy is a
process inside the agent container instead of a separate container.

**Pitfalls**:

- No instance on the node for that network means no namespace: its
  absence is normal on an idle node.
- The agent logs at DEBUG level on the lab; the log is large, filter it.
- The agent configuration is rendered on the node under
  `/var/lib/openstack/neutron-ovn-metadata-agent`; edits there are
  overwritten by the next `neutron-metadata` deployment.
- The path crosses the data plane **and** the control plane: a healthy
  agent with a failing `nova-metadata` pod gives HTTP 500 to the instance.

**See also**: [Data plane troubleshooting](../troubleshooting/dataplane.md),
[Logs](../operations/02-logs.md)

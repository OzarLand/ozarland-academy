# Network connectivity problems

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) for every read-only command run on the bastion, the OKD node and the compute node, the MetalLB allocation failures (reproduced with throwaway Services) and the missing NAD; not executed: the host cloud checks and `terraform` commands of scenario C (outside the lab perimeter of this validation), a real port-security or interface-rename fault, whereabouts exhaustion, and any MTU change

## In short

- Four networks, split the same way: `.10` the OKD node, `.30` to `.70`
  pod interfaces, `.80` to `.90` MetalLB addresses, `.100` and above
  compute nodes.
- MetalLB addresses and macvlan pods only work because port security is
  disabled on the three OpenStack networks. If it is enabled, every
  scenario of this page appears at once.
- Never test a MetalLB address with `ping`: test a TCP port from the
  compute node and read the neighbour entry.
- A NetworkAttachmentDefinition is read only when a pod is created: a
  missing one stays hidden until the next restart.
- MTU faults look like hangs on large transfers; probe with
  `ping -M do`.

Four networks matter to OpenStack in the lab. Knowing which one a flow uses
is half of the diagnosis.

| Network | Default CIDR | Carries | OKD node | Pods (NAD range) | Service IPs (MetalLB) | Compute nodes |
|---------|--------------|---------|----------|------------------|-----------------------|---------------|
| machine | 192.168.130.0/24 | Kubernetes API, Routes, pod network underlay | .10 | n/a | n/a | n/a |
| ctlplane | 192.168.122.0/24 | Ansible SSH to compute nodes, DNS for them | .10 | .30-.70 | .80-.90 (DNS on .80) | .100+ |
| internalapi | 172.17.0.0/24 | Internal API endpoints, RabbitMQ, OVN databases | .10 | .30-.70 | .80-.90 (APIs on .80, RabbitMQ on .85 and .86) | .100+ |
| tenant | 172.19.0.0/24 | Geneve tunnels between OVN chassis | .10 | .30-.70 | .80-.90 | .100+ |

Two mechanisms put control plane pods on the OpenStack networks:

- **MetalLB** gives a Service an address on a network and answers ARP for it
  from the node interface: the equivalent of a keepalived VIP.
- A **NetworkAttachmentDefinition** (NAD) gives a pod an extra interface
  (macvlan) with its own MAC and IP on a network.

Both make the OKD node send traffic with addresses that the host cloud did
not assign to its port. That only works because Neutron port security is
disabled on the three OpenStack networks of the lab. If it is enabled, all
of the scenarios below appear at once.

## Scenario A: LoadBalancer Service without an address

### 1. Initial symptoms

- `oc get svc` shows `<pending>` in `EXTERNAL-IP` for a Service of type
  `LoadBalancer`.
- The service resource stays `False` on `ExposeServiceReady`; RabbitMQ or the
  DNS service is not reachable from compute nodes.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get svc | grep -i loadbalancer
oc describe svc <service> | sed -n '/^Annotations:/,/^Selector/p;/^Events:/,$p'
oc -n metallb-system get pods
oc -n metallb-system get ipaddresspools,l2advertisements
oc -n metallb-system get ipaddresspool internalapi -o jsonpath='{.spec.addresses}{"\n"}'
oc get svc -o json | jq -r '.items[] | select(.spec.type=="LoadBalancer") | "\(.metadata.name)\t\(.metadata.annotations["metallb.universe.tf/address-pool"])\t\(.metadata.annotations["metallb.universe.tf/loadBalancerIPs"])\t\(.status.loadBalancer.ingress[0].ip // "PENDING")"' | column -t
oc -n metallb-system logs deployment/controller --since=15m | tail -30
```

### 3. Expected observations

Events on the Service give the reason, as a Warning `AllocationFailed`
from `metallb-controller`. The texts below were produced on the lab with
throwaway Services:

| Event message | Cause |
|---------------|-------|
| `Failed to allocate IP for "<ns>/<svc>": no available IPs` | The Service has no pool annotation (the pools do not auto-assign) |
| `... no available IPs in pool "<pool>"` | The pool is exhausted |
| `... ["172.17.0.200"] is not allowed in config` | The requested IP is outside every pool range |
| `... can't change sharing key for "<ns>/<svc>", address also in use by openstack/rabbitmq` | Two Services request the same IP without the same `allow-shared-ip` annotation, or with overlapping ports |
| `... unknown pool "<name>"` | The annotation names a pool that does not exist |
| No MetalLB pods, or `controller` not ready | MetalLB itself is down |

In a healthy lab:

- the six internal API Services (`keystone-internal`, `glance-default-internal`,
  `neutron-internal`, `nova-internal`, `nova-metadata-internal`,
  `placement-internal`) share 172.17.0.80 (same `allow-shared-ip` key,
  `internalapi`, different ports); `rabbitmq` uses 172.17.0.85,
  `rabbitmq-cell1` 172.17.0.86, and `dnsmasq-dns` uses 192.168.122.80;
- the events of a Service show `IPAllocated`, then `nodeAssigned`
  ("announcing from node "okd-0" with protocol "layer2""), and a Warning
  `deprecatedAnnotation` that is harmless;
- `metallb-system` has one `controller-...` and one `speaker-...` pod;
- three pools (`ctlplane`, `internalapi`, `tenant`, each `.80-.90`, auto
  assign `false`) and three L2 advertisements, each bound to one node
  interface.

### 4. Root cause

MetalLB assigns an address only if the pool named in the annotation exists,
contains the requested IP, and the IP is free or shareable. The pools are
`autoAssign: false`: a Service without annotations never gets an address.
The annotations come from `override.service` in the control plane resource,
so a typo there is the usual cause; a pool that is too small is the other.

### 5. Resolution

Wrong IP or pool name: fix `override.service` for that service in the
`OpenStackControlPlane` (and the template in the repository).

Pool too small: extend the range in
`deployment/okd/metallb/address-pools.yaml.tmpl` (keep clear of the pod range
.30-.70 and the compute node range .100+) and re-run the platform step:

**[CHANGE]**

```bash
scripts/bastion/04-platform-services.sh
```

MetalLB pods not running:

**[READ-ONLY]**

```bash
oc -n metallb-system describe pods | sed -n '/^Events:/,$p'
```

### 6. Verification

**[READ-ONLY]**

```bash
oc get svc | grep -i loadbalancer            # no <pending>
oc get openstackcontrolplane openstack
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100 \
  'getent hosts keystone-internal.openstack.svc; nc -vz 172.17.0.85 5671; ip neigh show 172.17.0.85'
```

Do not use `ping` to test a MetalLB address: on the lab the service
addresses never answer ICMP, healthy or not, and they are not reachable
from the bastion (it is not on the OpenStack networks). Test a TCP port from
the compute node, and look at the neighbour entry: it must show the MAC
address of the OKD node interface, in any state except `FAILED` or
`INCOMPLETE`.

### 7. Risks and precautions

- Changing the IP of the internal API or RabbitMQ Service changes endpoints
  that compute nodes already use: follow with a data plane deployment.
- Do not enable `autoAssign` on the pools to make the symptom go away; the
  services would get unpredictable addresses.

## Scenario B: pod stuck in ContainerCreating (network attachment)

### 1. Initial symptoms

- A pod that uses an OpenStack network stays in `ContainerCreating`. On the
  lab these are the two OVN database pods and the Neutron API pod
  (`internalapi`), and the Ansible runner pods of a data plane deployment
  (`ctlplane`).
- Or the service resource reports `NetworkAttachmentsReady=False`.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc describe pod <pod> | sed -n '/^Events:/,$p'
oc get network-attachment-definitions
oc get network-attachment-definitions internalapi -o jsonpath='{.spec.config}' | jq .
cat .work/okd-interfaces.env
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} --quiet -- chroot /host ip -br address
oc get pod <pod> -o jsonpath='{.metadata.annotations.k8s\.v1\.cni\.cncf\.io/networks}{"\n"}'
oc get pod <running-pod> -o jsonpath='{.metadata.annotations.k8s\.v1\.cni\.cncf\.io/network-status}' | jq .
oc get ippools.whereabouts.cni.cncf.io -A
```

### 3. Expected observations

| Observation | Cause |
|-------------|-------|
| Condition message `NetworkAttachment resources missing: internalapi` | The NAD does not exist in the `openstack` namespace (observed) |
| Pod events `NoNetworkFound`, "cannot find a network-attachment-definition (internalapi) in namespace (openstack)", then `FailedCreatePodSandBox` | Same cause, seen from the pod (observed) |
| Pod event about macvlan and a link that is not found | The `master` interface named in the NAD does not exist on the node (not reproduced) |
| Pod event mentioning `whereabouts` and an address that cannot be allocated | The pod range (.30-.70) is exhausted, often by leaked allocations (not reproduced) |

On a healthy lab:

- three definitions exist: `ctlplane`, `internalapi`, `tenant`. Each is a
  `macvlan` on one node interface (`master`), with `whereabouts` address
  management on the range `.30-.70`;
- `.work/okd-interfaces.env` names the three interfaces (for example
  `CTLPLANE_IFACE=ens4`, `INTERNALAPI_IFACE=ens5`, `TENANT_IFACE=ens6`) and
  they are the node interfaces that carry 192.168.122.10, 172.17.0.10 and
  172.19.0.10. The machine interface is enslaved to `br-ex`, which carries
  192.168.130.10;
- the whereabouts pools live in the `openshift-multus` namespace, one per
  range in use (`172.17.0.0-24`, and `192.168.122.0-24` once a data plane
  deployment has run). The allocations are in the pool:

  **[READ-ONLY]**

  ```bash
  oc -n openshift-multus get ippools.whereabouts.cni.cncf.io 172.17.0.0-24 -o json | jq -r '.spec.allocations | to_entries[] | "\(.key) \(.value.podref)"'
  ```

  The key is the offset in the range (`30` is 172.17.0.30).

### 4. Root cause

The extra interface is created by the CNI plugins on the node when the pod
sandbox is set up. If the definition is missing, names a wrong parent
interface, or has no free address, the sandbox cannot be created and the pod
never leaves `ContainerCreating`. A NAD is only read at pod creation:
changing it does not affect running pods.

Interface names are discovered at installation time. If the node comes up
with different names after a hardware change in the host cloud (an interface
detached and re-attached), the NADs and the MetalLB advertisements point at
the wrong device.

### 5. Resolution

Regenerate the interface mapping and re-apply the definitions (both steps
are idempotent):

**[CHANGE]**

```bash
scripts/bastion/04-platform-services.sh
scripts/bastion/06-openstack-controlplane.sh
```

Then recreate the stuck pod so that it picks up the corrected definition:

**[CHANGE]**

```bash
oc delete pod <pod>
```

Exhausted or leaked addresses: list the allocations (command above) and
compare with the pods that exist. The least risky way is to delete the
pods of the affected network one at a time so that allocations are released
properly. Cleaning a leaked allocation by hand was not executed during the
validation of this page; it was done on 2026-11-12 on a simulated leak,
with a JSON patch that tests the offset first: see
[how do I clean a leaked address](../knowledge-base/okd-networking.md#which-pod-holds-which-address-on-the-openstack-networks-and-how-do-i-clean-a-leaked-one).

### 6. Verification

**[READ-ONLY]**

```bash
oc get pods | grep -c ContainerCreating || true
oc get pod <pod> -o jsonpath='{.metadata.annotations.k8s\.v1\.cni\.cncf\.io/network-status}' | jq -r '.[] | "\(.name) \(.interface) \(.ips)"'
oc get openstackcontrolplane openstack
```

### 7. Risks and precautions

- Deleting an OVN database pod to re-attach it interrupts Neutron and the
  OVN controllers briefly. Do them one at a time.
- Do not edit a NAD and expect running pods to change; plan the pod
  restarts.

## Scenario C: compute node cannot reach the control plane

### 1. Initial symptoms

- `nova-compute` is `down`, OVN agents are not alive, or a data plane
  deployment fails with timeouts to 172.17.0.x.
- From the compute node, 172.17.0.80 or 172.17.0.85 does not answer.

### 2. Read-only investigation

On the bastion:

**[READ-ONLY]**

```bash
oc get svc | grep -i loadbalancer
oc -n metallb-system get l2advertisements          # pool and interface of each advertisement
oc -n metallb-system logs daemonset/speaker --since=10m | grep -i 'announc\|withdraw\|error' | tail
oc get network.operator cluster -o jsonpath='{.spec.defaultNetwork.ovnKubernetesConfig.gatewayConfig}{"\n"}'
```

On the compute node (`ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100`):

**[READ-ONLY]**

```bash
ip -br address
ip route
ping -c 2 172.17.0.10          # the OKD node on internalapi: plain layer 2
nc -vz 172.17.0.85 5671        # RabbitMQ (TLS), a MetalLB address
nc -vz 172.17.0.80 5000        # Keystone internal, a MetalLB address
ip neigh show 172.17.0.80      # which MAC answered
sudo ovs-vsctl get open . external_ids:ovn-remote
sudo podman logs --tail 30 ovn_controller 2>&1 | grep -i 'connect\|error'
```

On the OKD node, check whether the packets arrive. `tcpdump` is not
installed on the node itself; it is in the debug container, so this command
does not use `chroot /host`:

**[READ-ONLY]**

```bash
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} --quiet -- timeout 15 tcpdump -ni <internalapi-interface> -c 5 host 172.17.0.100
```

What a healthy lab answers:

- on the compute node, `eth0` is enslaved to `br-ex` (192.168.122.100),
  `eth1` carries 172.17.0.100 and `eth2` 172.19.0.100;
- the ping to 172.17.0.10 answers; both `nc` commands report a successful
  connection; the neighbour entry of 172.17.0.80 shows the MAC address of
  the node interface. **A ping to a MetalLB address does not answer even
  when everything works**: do not use it as a test;
- `ovn-remote` is `ssl:ovsdbserver-sb.openstack.svc:6642`: the OVN
  controller reaches the southbound database by name, through the lab DNS
  service, on a pod address of the internalapi range;
- the gateway configuration shows `routingViaHost: true` and
  `ipForwarding: Global`;
- the speaker log shows `serviceAnnounced` events for the addresses it
  owns. Lines with `notOwner` or `serviceWithdrawn` are normal when a
  Service is created or deleted.

### 3. Expected observations

Work through the layers:

| Test | Fails | Meaning |
|------|-------|---------|
| Ping the node address (.10) | Yes | No layer 2 between the two VMs on that network: wrong network attachment, interface down, or wrong address on the compute node |
| TCP to a MetalLB address | Yes, while the node address answers, and `ip neigh` shows `FAILED` or `INCOMPLETE` | Nobody answers ARP for the service IP: MetalLB speaker not announcing on that interface, **or the host cloud drops the ARP reply (port security)** |
| ARP resolves to the node MAC but TCP fails | | IP forwarding from the node interface to the pod network is not enabled (`ipForwarding` must be `Global`, `routingViaHost` `true`), or the Service has no ready endpoint |
| The node address and service IPs work, but pod addresses (.30-.70, for example the OVN southbound database) fail | | Traffic from macvlan pods uses MAC addresses unknown to the host cloud: **port security** again |
| tcpdump on the node shows requests but the compute node never sees replies | | Replies are dropped after leaving the node: port security |

### 4. Root cause

In order of likelihood on this lab:

1. **Port security in the host cloud.** Neutron anti-spoofing only lets a
   port send and receive traffic for the MAC and IP it was created with.
   MetalLB addresses are extra IPs on the node MAC; macvlan pods are extra
   MACs. Both are dropped silently unless port security is disabled on the
   port (the lab disables it on the whole network) or allowed address pairs
   are set. Symptoms are selective, which makes it confusing: the node
   address works, everything else does not.
2. **Forwarding not enabled** in OVN-Kubernetes: service traffic arriving on
   a secondary interface is not forwarded to the pod network.
3. **Wrong interface** in the MetalLB advertisement after an interface
   rename (see scenario B).
4. **Compute node network configuration** not applied or wrong order of
   interfaces (ctlplane, internalapi, tenant must be the first, second and
   third NIC).

### 5. Resolution

Port security is fixed in the host cloud, from the workstation. Check, then
let Terraform restore the declared state (these three commands and the
`apply` were not executed during the validation of this page):

**[READ-ONLY]**

```bash
openstack network show okdlab-internalapi -c port_security_enabled
openstack port list --network okdlab-internalapi --long -c Name -c "Fixed IP Addresses" -c "Port Security Enabled"
terraform -chdir=deployment/infrastructure plan
```

**[CHANGE]**

```bash
terraform -chdir=deployment/infrastructure apply
```

Forwarding and MetalLB advertisement: re-run the platform step.

**[CHANGE]**

```bash
scripts/bastion/04-platform-services.sh
```

Compute node network configuration: run the network services again.

**[CHANGE]** May briefly interrupt connectivity of the compute node.

```bash
cat <<'YAML' | oc apply -f -
apiVersion: dataplane.openstack.org/v1beta1
kind: OpenStackDataPlaneDeployment
metadata:
  name: edpm-network-fix-1
  namespace: openstack
spec:
  nodeSets:
    - openstack-edpm
  servicesOverride:
    - configure-network
    - validate-network
YAML
```

### 6. Verification

From the compute node:

**[READ-ONLY]**

```bash
nc -vz 172.17.0.85 5671 && nc -vz 172.17.0.80 5000
```

From the bastion:

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack compute service list
oc rsh openstackclient openstack network agent list
```

### 7. Risks and precautions

- Never "fix" this by enabling masquerading or adding static ARP entries on
  the nodes; the cause stays and the next address fails.
- Disabling port security removes the security groups of the host cloud on
  those ports. That is acceptable on isolated lab networks without a
  gateway; it is why the machine network, which is routed, keeps port
  security enabled.
- tcpdump on the node is read-only but verbose; always use `-c` and a
  `timeout`, or the debug pod waits forever on a silent interface.

## Scenario D: MTU

### 1. Initial symptoms

- Small requests work, large ones hang: `openstack token issue` succeeds but
  image uploads, large API responses or SSH sessions inside instances stall.
- TLS handshakes time out on one path only.
- Instances get an address but large pings fail.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
grep MTU .work/infra.env
oc get network.config cluster -o jsonpath='{.status.clusterNetworkMTU}{"\n"}'
oc debug node/${node} --quiet -- chroot /host ip -o link | awk '{print $2,$4,$5}' | grep -v veth
oc get netconfig netconfig -o json | jq -r '.spec.networks[] | "\(.name) \(.mtu)"'
oc get oscp openstack -o jsonpath='{.spec.neutron.template.customServiceConfig}{"\n"}'
oc rsh openstackclient openstack network show <network> -c mtu
```

(`ip -br link` does not print the MTU, and `openstack network list` has no
MTU column: hence `ip -o link` and `network show`.)

Probe a path with the don't-fragment bit (payload = MTU minus 28):

**[READ-ONLY]**

```bash
# On the compute node, towards the OKD node on the tenant network, for an MTU of 1442:
ping -c 2 -M do -s 1414 172.19.0.10
ping -c 2 -M do -s 1415 172.19.0.10     # must fail: "message too long"
```

### 3. Expected observations

- All lab networks have the MTU of the host cloud tenant networks (below
  1500 when the host cloud uses an overlay; the value is in `infra.env`).
- The cluster network MTU is 100 bytes lower (OVN-Kubernetes Geneve
  overhead).
- Neutron `global_physnet_mtu` and `path_mtu` equal the tenant network MTU,
  and OpenStack tenant networks are another 58 bytes lower (Geneve inside
  the lab).
- The largest non-fragmenting ping matches the interface MTU on every hop.

Values measured on the lab, where the host cloud gives 1442: `infra.env`,
the node interfaces, `NetConfig` and the two Neutron options all say 1442;
the cluster network MTU is 1342; a new Geneve tenant network gets 1384. From
the compute node, `ping -M do -s 1414 172.19.0.10` answers and `-s 1415`
fails with "message too long".

### 4. Root cause

The lab is an overlay (OpenStack tenant networks) inside an overlay (pod
network or OVN tunnels) inside an overlay (the host cloud). Each layer
subtracts its header. If any layer believes it has 1500 bytes when the path
has fewer, full-size packets are dropped, and because path MTU discovery
relies on ICMP messages that are often filtered, connections hang instead of
failing fast.

### 5. Resolution

Find the layer whose configured MTU exceeds the layer below it and correct
it at its source: node interfaces (installer network configuration),
`NetConfig` and Neutron (control plane template, rendered from `infra.env`),
compute node interfaces (data plane deployment). Existing OpenStack networks
keep the MTU they were created with:

**[CHANGE]**

```bash
oc rsh openstackclient openstack network set --mtu <value> <network>
```

Instances pick up the new value on DHCP renewal or reboot.

### 6. Verification

Repeat the don't-fragment pings on every hop, then a large transfer:

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack image list
```

### 7. Risks and precautions

- Changing the cluster network MTU of OKD is a disruptive, multi-step
  procedure with node reboots. Get it right at installation.
- Never raise an MTU to "see if it helps"; only lower towards the measured
  path MTU.

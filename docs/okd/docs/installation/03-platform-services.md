# Step 3 — Platform services

**Where:** bastion. **Command:** `scripts/bastion/04-platform-services.sh`

## What we deploy

Four things the OpenStack operators expect from the platform and that a
fresh OKD cluster lacks.

| Component | Why OpenStack needs it | Kolla-Ansible analogy |
|---|---|---|
| IP forwarding / host routing in OVN-Kubernetes | Traffic from compute nodes must enter through the node's secondary NICs and reach pods | `net.ipv4.ip_forward` on controllers |
| Local PersistentVolumes + `local-storage` StorageClass | Databases, RabbitMQ, OVN databases and Glance need storage that outlives pods | Docker named volumes (`mariadb`, `rabbitmq`, ...) |
| cert-manager | Issues internal CAs and a certificate per service endpoint; TLS is on by default | `kolla-ansible certificates` |
| MetalLB | Gives selected Services a stable address on the OpenStack networks | keepalived + HAProxy internal VIP |

On Red Hat OpenShift these come from the vendor operator catalog. OKD does
not have that catalog, so the lab installs the upstream releases directly,
at versions pinned in `lab.env`.

## What the script does, in order

1. **Finds the interface names.** The installer knows interfaces by MAC
   address; MetalLB and network attachments need kernel names. The script
   looks up which interface carries each OpenStack network address and
   records the result in `.work/okd-interfaces.env`.
2. **Patches the cluster network operator**
   (`routingViaHost: true`, `ipForwarding: Global`).
3. **Creates the storage.** Directories under `/var/lib/openstack-lab-pv/`
   on the node, with the SELinux type containers may write to, then one
   `PersistentVolume` object per directory.
4. **Installs cert-manager** from its release manifest and waits.
5. **Installs MetalLB** from its release manifest, grants its service
   accounts the Security Context Constraints they need on OKD, then creates
   one address pool per OpenStack network, announced only on the matching
   interface.
6. **Installs the `FRRConfiguration` CRD** of the frr-k8s project, at the
   version pinned by `FRR_K8S_VERSION`. The lab does not use BGP and
   installs no FRR daemon, but the OpenStack infra operator watches this
   kind and does not start without it; the upstream MetalLB manifest does
   not ship it.

The first run takes about a minute and a half. A second run takes a few
seconds and reports every object as unchanged.

## Concepts worth understanding here

- **PersistentVolume / PersistentVolumeClaim / StorageClass.** A PV is a
  piece of storage that exists; a PVC is a request for storage made by a
  workload; the StorageClass is how they find each other. Here PVs are
  created in advance and wait in state `Available`:

  **[READ-ONLY]**

  ```bash
  oc get pv
  ```

  After step 5 some will be `Bound` to claims such as
  `mysql-db-openstack-galera-0`. See
  [../concepts/02-kubernetes-building-blocks.md](../concepts/02-kubernetes-building-blocks.md).
- **Security Context Constraints (SCC).** OKD refuses by default pods that
  want host networking or a fixed UID. Upstream manifests written for plain
  Kubernetes often need an explicit SCC grant, which is what the two
  `oc adm policy add-scc-to-user` commands do. A pod rejected by SCC never
  starts; the reason is in the events of its ReplicaSet or DaemonSet.
- **Layer 2 advertisement.** MetalLB does not route. It makes the node
  answer ARP for the service address on one interface. If the host cloud
  filtered that ARP reply (port security), the address would simply be dead.

## Verify

**[READ-ONLY]**

```bash
oc get storageclass
oc get pv
oc -n cert-manager get pods
oc -n metallb-system get pods
oc -n metallb-system get ipaddresspools,l2advertisements
oc get network.operator cluster -o jsonpath='{.spec.defaultNetwork.ovnKubernetesConfig.gatewayConfig}{"\n"}'
```

Expected: the `local-storage` class (`kubernetes.io/no-provisioner`) and 12
PVs `Available`; three cert-manager pods and the MetalLB `controller` and
`speaker` pods `Running`; three pools and three L2 advertisements
(`ctlplane`, `internalapi`, `tenant`); a gateway configuration with
`"ipForwarding":"Global"` and `"routingViaHost":true`.

**[READ-ONLY]**

```bash
oc get crd frrconfigurations.frrk8s.metallb.io
```

## If something fails

| Symptom | Look at |
|---|---|
| "No interface carries ..." | The node's secondary NICs did not get their static addresses: `oc debug node/<node> -- chroot /host ip -br address` and compare with `.work/infra.env` |
| MetalLB pods not created | `oc -n metallb-system get events --sort-by=.lastTimestamp` — an SCC denial names the missing permission |
| Address pools rejected | The MetalLB webhook is not ready yet (the script retries for 3 minutes); `oc -n metallb-system logs deploy/controller` |
| Cluster operators `Progressing` after the network patch | Expected for a few minutes: OVN-Kubernetes restarts its node components |

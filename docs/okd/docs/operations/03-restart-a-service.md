# Restart a service

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

The Kolla reflex is `docker restart nova_api` on each controller. The
equivalent here is to **delete the pod**: the Deployment or StatefulSet that
owns it immediately starts a replacement with the same configuration. You
never "start" or "stop" a pod; you let the controller recreate it.

## 1. Initial symptoms

- A service misbehaves (hung worker, stale connection to the database or
  RabbitMQ after an infrastructure incident) and you want a clean process.
- You want to observe what a restart does to the service before you need it
  in anger.

A restart is **not** how configuration is applied: a configuration change
made through the control plane resource rolls the pods by itself
(see [04](04-change-service-configuration.md)).

## 2. Read-only investigation

Know what you are about to restart: its kind, its replica count, and whether
it holds data.

**[READ-ONLY]**

```bash
oc get pods -l service=keystone -o wide
oc get deployments,statefulsets
oc get pod <pod> -o jsonpath='{range .metadata.ownerReferences[*]}{.kind}/{.name}{"\n"}{end}'
oc get pvc
```

## 3. Expected observations

| Workload kind | Examples in the lab | Pod names | Data |
|---------------|--------------------|-----------|------|
| Deployment | Keystone, Placement, Neutron, dnsmasq | Random suffix (`keystone-7b45c49ccb-fj7ct`) | None in the pod |
| StatefulSet | Galera, RabbitMQ, memcached, Glance, Nova services, OVN databases and northd | Stable ordinal (`nova-api-0`) | Galera, RabbitMQ, Glance and the OVN databases have a PVC |

The lab control plane has no DaemonSet. With one replica (the lab default)
any restart is a short outage of that service. Durations measured on the
lab, from the delete to the new pod being ready:

| Pod deleted | Back to ready after | Seen meanwhile |
|-------------|---------------------|----------------|
| Keystone | about 35 s | Authentication fails; the control plane resource stays `True` |
| Placement | about 25 s | |
| `nova-scheduler-0`, `nova-cell1-conductor-0` | about 35 s | |
| `rabbitmq-server-0` | about 60 s | Control plane `False` with a Nova message for about 50 s, then `True` by itself |
| `openstack-galera-0` | about 20 s | `Galera/openstack` goes `Unknown` then `True`; the control plane resource did not leave `True` |

Most of the delay is the readiness probe of the new pod, not the start of
the process.

## 4. Root cause

What actually happens on a restart:

- **Deployment pod deleted**: the ReplicaSet sees one pod missing and creates
  a new one with a new name. The old pod receives SIGTERM and has a grace
  period to finish requests.
- **StatefulSet pod deleted**: the same pod name is recreated (`nova-api-0`
  again) and re-attached to the same PVC if it has one. Data survives
  because it lives in the volume, not in the pod.
- **`oc rollout restart`**: adds a timestamp annotation to the pod template.
  The template is owned by an operator, which removes the annotation within
  a second. Observed on the lab: on a Deployment (Keystone) the new
  ReplicaSet is created and scaled back to zero before its pod is ready, so
  the running pod is **not** restarted at all; on a StatefulSet
  (`nova-scheduler`) the pod is restarted once. Do not use it: the result
  depends on the workload kind. Delete the pod instead.
- **Scaling to 0 and back**: the operator owns `replicas`; a manual
  `oc scale` on the Deployment is reverted in under a second. To stop a
  service on purpose, set `replicas: 0` in the `OpenStackControlPlane`.

The Service (ClusterIP or MetalLB address) and the Route are separate
objects. They are not touched by a pod restart, so endpoints, VIPs and DNS
names stay the same; traffic resumes when the new pod passes its readiness
probe.

## 5. Resolution

### Stateless API service (Keystone, Placement, Neutron, Nova API, Glance)

**[CHANGE]** Short API outage with one replica.

```bash
oc delete pod -l service=keystone
oc get pods -l service=keystone -w        # Ctrl-C once Running and ready
```

### Nova control services

**[CHANGE]**

```bash
oc delete pod nova-scheduler-0
oc delete pod nova-cell1-conductor-0
```

### RabbitMQ or Galera

Restart these only with a reason, one pod at a time, and wait for `1/1`
before touching anything else. With a single replica every dependent service
loses its connection and must reconnect.

**[CHANGE]** Interrupts every OpenStack service for the duration of the restart.

```bash
oc delete pod rabbitmq-server-0
oc get pod rabbitmq-server-0 -w
```

**[CHANGE]** Interrupts every OpenStack API for the duration of the restart.

```bash
oc delete pod openstack-galera-0
oc get pod openstack-galera-0 -w
```

If the Galera pod does not come back to `1/1`, do not delete it again: read
[Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md).

### nova-compute on a compute node

Compute nodes are outside Kubernetes; the Kolla reflex applies, with systemd
instead of docker.

**[CHANGE]** Running instances keep running; the node is unmanageable until
nova-compute is back.

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100 sudo systemctl restart edpm_nova_compute
```

### Stop a service deliberately

The Deployment goes to `0/0` within three seconds and comes back in about
25 seconds. While it is at zero the control plane resource stays `True`:
nothing in the conditions tells you that Placement is stopped.

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"placement":{"template":{"replicas":0}}}}'
# ... and back
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"placement":{"template":{"replicas":1}}}}'
```

## 6. Verification

**[READ-ONLY]**

```bash
oc get pods -l service=keystone                 # new AGE, READY 1/1, RESTARTS 0
oc get openstackcontrolplane openstack          # back to True
oc rsh openstackclient openstack token issue
oc rsh openstackclient openstack compute service list
```

## 7. Risks and precautions

- Never use `oc delete pod --force --grace-period=0` on Galera, RabbitMQ or
  the OVN databases: it skips clean shutdown and can leave the data
  directory in a state that needs manual recovery.
- Never delete the PVC to "really" restart a stateful service: that is data
  loss, not a restart (see [storage](../troubleshooting/storage.md)).
- Do not delete the Deployment or StatefulSet itself to restart. The operator
  recreates it, but for a StatefulSet this is a needlessly risky way to get
  the same result.
- Do not restart several infrastructure services at once. Restart one, wait
  for the control plane to return to `True`, then the next.
- A restart clears symptoms and evidence. Save the logs first
  (`oc logs <pod> > file`): once the pod is deleted they are gone.
- Restarting an operator pod (`openstack-operators` namespace) is harmless
  for running services; it pauses reconciliation for about 15 seconds, and
  the operator then reconciles everything it owns once, which removes any
  manual drift it finds.

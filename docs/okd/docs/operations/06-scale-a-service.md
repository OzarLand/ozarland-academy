---
title: "Scale a service"
description: "In Kolla-Ansible the number of API instances is the number of hosts in an inventory group. Here it is a replicas field."
---

# Scale a service

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

In Kolla-Ansible the number of API instances is the number of hosts in an
inventory group. Here it is a `replicas` field. On a single-node lab scaling
brings no resilience (all replicas die with the node), but it is the cheapest
way to see how Services spread traffic and how rolling updates stop being
outages.

## In short

- The number of API pods is the `replicas` field of the service in the
  control plane resource. Scaling the Deployment directly is reverted.
- Nothing else has to be reconfigured: the Service adds the new pod as an
  endpoint once it is ready.
- With two Keystone replicas, 12 token requests out of 12 succeeded on the
  lab while one pod was replaced.
- Leave Galera, RabbitMQ and the OVN databases at 1 on the lab.

## 1. Initial symptoms

- You want an API to stay available while its pods are being replaced.
- An API pod is saturated (rare in a lab).

## 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get deployments,statefulsets
oc get oscp openstack -o jsonpath='{.spec.keystone.template.replicas}{"\n"}'
oc adm top node
oc adm top pods --sort-by=memory | head -20
oc get endpointslices -l 'kubernetes.io/service-name in (keystone-internal,keystone-public)'
```

`oc get endpoints keystone-internal` still works but prints a deprecation
warning on this Kubernetes version (`v1 Endpoints is deprecated in v1.33+;
use discovery.k8s.io/v1 EndpointSlice`).

## 3. Expected observations

- Every workload is `1/1`.
- The Keystone Services each list one endpoint address (the pod IP).
- Node memory usage leaves room for one more pod of the service you scale.
  Measured per pod on the idle lab: Neutron API about 490 MiB, Glance 480,
  Keystone 430, Nova API 310, Nova metadata 250, Placement 250.

## 4. Root cause

`replicas` flows the usual way: control plane resource, service resource,
Deployment. The Deployment starts more identical pods; the Service notices
them through their labels and adds them as endpoints once they pass their
readiness probe. Nothing else has to be reconfigured: the MetalLB address,
the Route and the Keystone endpoint URLs all point at the Service, not at
pods. This replaces the HAProxy backend list of a Kolla deployment.

Why scaling the Deployment directly does not work: `replicas` on the
Deployment is owned by the operator and is reset to the value in the service
resource.

Why stateful services are different:

- **Galera** replicas form a cluster. Valid sizes are 1 or 3. Going from 1 to
  3 makes two new members copy the full dataset; going back is not a simple
  reduction. With local volumes on one node, three members also consume three
  persistent volumes and give no real redundancy.
- **RabbitMQ** replicas form a cluster too; changing the size of a running
  cluster reshuffles queues. Treat it as a maintenance operation.
- **OVN databases** use Raft: 1 or 3.

On the lab, leave all of these at 1.

## 5. Resolution

**[CHANGE]** Adds one Keystone pod; no interruption. The control plane
reports `False`, "KeystoneAPI: Deployment in progress", for about 30 seconds
until the second pod is ready.

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"keystone":{"template":{"replicas":2}}}}'
oc get pods -l service=keystone -w
```

Scale back:

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"keystone":{"template":{"replicas":1}}}}'
```

Scaling back takes about three seconds: one pod is terminated, nothing is
restarted.

Nova API works the same way under
`spec.nova.template.apiServiceTemplate.replicas`, Neutron under
`spec.neutron.template.replicas`.

## 6. Verification

**[READ-ONLY]**

```bash
oc get deployment keystone                        # READY 2/2
oc get endpointslices -l kubernetes.io/service-name=keystone-internal   # two addresses
oc get openstackcontrolplane openstack            # True
for i in 1 2 3 4; do oc rsh openstackclient openstack token issue -f value -c expires; done
```

With two replicas, repeat a restart from [03](03-restart-a-service.md) on one
pod while issuing tokens in a loop: there should be no failed request.
Observed on the lab: 12 token requests out of 12 succeeded while one of the
two pods was deleted and replaced.

## 7. Risks and precautions

- More replicas is more memory. Scale one service, then look at
  `oc adm top node`.
- More API replicas means more database connections; with many services
  scaled, the Galera connection limit becomes the next bottleneck.
- Do not change Galera, RabbitMQ or OVN database replicas on a lab you want
  to keep, unless that is the exercise and you accept a rebuild.
- Replica counts set by hand are lost when the deployment script re-applies
  the template; put lasting values in the template.

---

**Previous:** [Enable a service](05-enable-a-service.md) · **Up:** [Operations guide](index.md) · **Next:** [Passwords and secrets](07-passwords-and-secrets.md)

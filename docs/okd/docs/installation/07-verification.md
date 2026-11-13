# Step 7 — Verification

**Where:** bastion.

## Smoke test

**[READ-ONLY]**

```bash
tests/smoke-test.sh
```

The script checks each layer from the bottom up and prints one line per
check:

| Layer | Checks |
|---|---|
| OKD | nodes Ready; cluster operators Available and not Degraded |
| Platform | local volumes usable; cert-manager and MetalLB running |
| Operators | ClusterServiceVersion Succeeded; `OpenStack` resource Ready |
| Control plane | `OpenStackControlPlane` Ready; pods healthy; LoadBalancer addresses assigned; Keystone issues a token; catalog populated |
| Data plane | NodeSet Ready; nova-compute up; OVN agents alive |

On the lab it prints 15 `PASS` lines and one `SKIP` (the functional test)
in about ten seconds. The exit code is the number of failed checks.

The order of the checks is also the order in which to investigate a broken
lab: a failure in a lower layer usually explains the ones above it.

## Functional test

**[CHANGE]** — creates an image, a flavor, a network and an instance in the
lab cloud, then deletes them:

```bash
tests/smoke-test.sh --functional
```

It uploads a CirrOS image, boots one instance on a tenant network and waits
for `ACTIVE`. This exercises Keystone, Glance, Placement, Neutron/OVN, the
nova scheduler and conductor, RabbitMQ on the internalapi network and the
compute node end to end. With KVM the whole test takes about a minute (the
instance is `ACTIVE` in ten seconds). With QEMU emulation, allow a few
minutes.

## Using the cloud

The `openstackclient` pod is preconfigured with the admin credentials:

**[READ-ONLY]**

```bash
oc -n openstack rsh openstackclient
openstack catalog list
```

Public endpoints are Routes under `*.apps.<cluster domain>`. They resolve
and are reachable from the bastion and from the lab networks only.

## Where to go next

1. [../concepts/](../concepts/README.md) — if you skipped it.
2. [../operations/](../operations/README.md) — the Day-2 guide; start with
   `01-inspect-service-status.md`.
3. [../troubleshooting/](../troubleshooting/README.md) — runbooks, several
   with a "reproduce it in the lab" section.
4. [../lifecycle/](../lifecycle/README.md) — updates, upgrades, backup.

---

**Previous:** [Step 6 — OpenStack data plane](06-openstack-data-plane.md) · **Up:** [Installation guide](README.md) · **Next:** [Operating OpenStack on OKD (Day 2)](../operations/README.md)

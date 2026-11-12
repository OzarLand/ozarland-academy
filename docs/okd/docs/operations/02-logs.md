# Logs

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

With Kolla-Ansible, service logs are files under `/var/log/kolla/<service>/`
on each host. Here control plane services write to the container's standard
output, and Kubernetes keeps that stream per container. There is one more
log to know about that has no Kolla equivalent: the **operator** log, which
tells you why a service was (or was not) deployed or reconfigured.

## 1. Initial symptoms

- An API returns 500 or a timeout and you need the traceback.
- A pod restarted and you want to know why.
- A condition says `Error` and the message is not enough.
- An Ansible run on a compute node failed.

## 2. Read-only investigation

### Service logs (control plane)

**[READ-ONLY]**

```bash
# Find the pod and its containers.
oc get pods -l service=keystone
oc get pod <pod> -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}'

# Current logs, follow, last hour, with timestamps.
oc logs <pod>
oc logs <pod> -c <container> -f
oc logs <pod> --since=1h --timestamps

# All pods of a service at once.
oc logs -l service=nova-api --all-containers --prefix --tail=100

# Through the workload instead of the pod name.
oc logs deployment/keystone
oc logs statefulset/nova-api -c nova-api-api
```

Many pods have two containers, and the split is not the same everywhere.
Names observed on the lab:

| Pod | Containers | Where the service log is |
|-----|------------|--------------------------|
| `keystone-...` | `keystone-api` | The only container: Apache access lines and Keystone messages together |
| `nova-api-0` | `nova-api-log`, `nova-api-api` | `nova-api-log` has the Nova log (requests, tracebacks); `nova-api-api` has the Apache access log |
| `nova-metadata-0` | `nova-metadata-log`, `nova-metadata-metadata` | Same split |
| `placement-...` | `placement-log`, `placement-api` | Same split |
| `glance-default-single-0` | `glance-log`, `glance-httpd` | Same split |
| `neutron-...` | `neutron-api`, `neutron-httpd` | `neutron-api` has the Neutron log, `neutron-httpd` the TLS front end |
| `nova-scheduler-0`, `nova-cell1-conductor-0` | `nova-scheduler-scheduler`, `nova-cell1-conductor-conductor` | The only container |
| `openstack-galera-0` | `galera` (init container `mysql-bootstrap`) | `galera` |
| `rabbitmq-server-0` | `rabbitmq` (init container `setup-container`) | `rabbitmq` |
| `ovsdbserver-nb-0`, `ovn-northd-0` | `ovsdbserver-nb` or `ovn-northd`, plus `openstack-network-exporter` | The first container |

If one container is quiet, look at the other. The Nova containers log at
`DEBUG` level by default on this version.

### Logs of a container that crashed

**[READ-ONLY]**

```bash
oc logs <pod> -c <container> --previous
oc describe pod <pod>      # "Last State", exit code, and the events
```

### Operator logs

**[READ-ONLY]**

```bash
oc -n openstack-operators get deployments
oc -n openstack-operators logs deployment/keystone-operator-controller-manager --since=30m
# Only what concerns one resource:
oc -n openstack-operators logs deployment/keystone-operator-controller-manager --since=30m | grep -i 'error\|keystone'
# The operator that turns the OpenStackControlPlane into service resources:
oc -n openstack-operators logs deployment/openstack-operator-controller-manager --since=30m
```

Operator Deployment names follow `<service>-operator-controller-manager`
(`keystone`, `nova`, `neutron`, `glance`, `ovn`, `mariadb`, `infra`, ...);
the first command lists them all. Placement is handled by the nova operator
(there is no placement operator Deployment), RabbitMQ, memcached and dnsmasq
by the infra operator, Galera by the mariadb operator. The data plane
controllers (NodeSet, deployment) run inside
`openstack-operator-controller-manager`.

An operator pod can also be selected by label:

**[READ-ONLY]**

```bash
oc -n openstack-operators logs -l openstack.org/operator-name=keystone --tail=50
```

### Job logs (db-sync, bootstrap)

**[READ-ONLY]**

```bash
oc get jobs,cronjobs
oc logs job/keystone-db-sync
oc logs job/keystone-bootstrap
```

On a healthy lab the last two commands answer `jobs.batch
"keystone-db-sync" not found`: the operators delete these Jobs as soon as
they succeed, and their log goes with them. Only a Job that failed or is
still running can be read. What remains listed are the periodic Jobs
(`keystone-cron-<n>`, created every hour by the CronJob `keystone-cron`) and
the data plane Jobs.

### Events

Events are the platform's own log: scheduling, image pulls, volume mounts,
probe failures. They expire after about an hour.

**[READ-ONLY]**

```bash
oc get events --sort-by=.lastTimestamp
oc get events --field-selector involvedObject.name=<pod>
```

### Data plane Ansible logs

Each data plane service runs as one Job; its pod log is the Ansible output.

**[READ-ONLY]**

```bash
oc get pods -l app=openstackansibleee
oc get pods -l openstackdataplanedeployment=edpm-deployment
oc logs -l openstackdataplanedeployment=edpm-deployment,openstackdataplaneservice=nova --tail=200
oc logs job/nova-edpm-deployment-openstack-edpm --tail=200
```

Jobs are named `<service>-<deployment>-<nodeset>`
(`nova-edpm-deployment-openstack-edpm`); the only exception on the lab is
`ssh-known-hosts-edpm-deployment`, which is not tied to a NodeSet.

### Compute node logs

On the compute node the services are podman containers managed by systemd
units named `edpm_<container>.service`. Reach the node from the bastion with
the data plane key.

**[READ-ONLY]**

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100

# On the node:
sudo podman ps
systemctl list-units 'edpm_*' 'virt*'
sudo systemctl status edpm_nova_compute
sudo journalctl -u edpm_nova_compute --since "1 hour ago"
sudo podman logs --tail 200 nova_compute
sudo ls /var/log/libvirt/qemu/ /var/log/openvswitch/
```

What runs on the lab compute node:

| Component | Runs as | Log |
|-----------|---------|-----|
| nova-compute | podman container `nova_compute`, unit `edpm_nova_compute.service` | `journalctl -u edpm_nova_compute` or `podman logs nova_compute` |
| OVN controller | podman container `ovn_controller`, unit `edpm_ovn_controller.service` | `journalctl -u edpm_ovn_controller` |
| OVN metadata agent | podman container `ovn_metadata_agent`, unit `edpm_ovn_metadata_agent.service` | `journalctl -u edpm_ovn_metadata_agent` |
| libvirt | host services, not containers: `virtqemud`, `virtlogd`, `virtnodedevd`, `virtsecretd`, `virtproxyd` (socket-activated), grouped by `edpm_libvirt.target` | `journalctl -u virtqemud`; one file per instance in `/var/log/libvirt/qemu/` |
| Open vSwitch | host services `ovs-vswitchd`, `ovsdb-server` | `/var/log/openvswitch/` |

The containers log to the journal: there is no `/var/log/containers/`
directory and no per-service file under `/var/log/` for Nova or OVN. A
fourth container, `nova_compute_init`, shows as `Exited (0)` in `podman ps
-a`; it runs once before `nova_compute` and that state is normal.

### Collect everything for later analysis

**[CHANGE]** (does not modify OpenStack or its resources, but creates a
temporary namespace and collection pod, pulls an image, and writes an archive
in the current directory on the bastion)

```bash
oc adm must-gather --image=quay.io/openstack-k8s-operators/openstack-must-gather:latest
```

On the lab the collection took about two and a half minutes and wrote 74 MB
into `must-gather.local.<id>/`. The image is pulled by the node like any
other, so it works behind the cluster-wide proxy without extra options.

## 3. Expected observations

- A healthy API pod logs one access line per request and periodic health
  probe hits.
- A Keystone pod logs one `GET /v3 ... "kube-probe/1.35"` line every few
  seconds: these are the health probes, not user traffic.
- An operator only logs when it reconciles. On an idle, healthy lab
  `--since=30m` often prints nothing at all; that is the normal case. During
  a reconciliation it prints lines such as `Reconciled Service
  successfully`. A few `ERROR Reconciler error` lines from the first minutes
  of the deployment (a dependency that was not there yet) are normal; errors
  that repeat now are not.
- `--previous` answers `previous terminated container "keystone-api" in pod
  ... not found` if the container never restarted; that is the normal case.
- Ansible Job pods end in `Completed`; the log ends with a `PLAY RECAP` line
  for `edpm-compute-0` with `unreachable=0` and `failed=0`.

## 4. Root cause

Why the layout differs from Kolla:

- Pods are disposable. A log file inside a pod dies with it, so services log
  to stdout and the node keeps the stream. When a pod is **deleted**, its
  logs go with it; only `--previous` (same pod, previous container) survives
  a restart. For history you need the events, the operator log, or a log
  collector (not part of this lab).
- A service is configured by an operator, so "why is my option not applied"
  is answered by the operator log, not by the service log.
- Compute nodes are not Kubernetes nodes. They are configured by Ansible and
  run podman, so their logs are where a Kolla operator expects: on the host.

## 5. Resolution

Reading logs resolves nothing by itself. Typical next steps:

- Traceback mentioning a refused or timed-out connection to the database or
  RabbitMQ: [Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md).
- Configuration parse error at start-up:
  [Pod Pending or CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md).
- Operator log with repeated errors on the same resource:
  [Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md).

To get more detail, raise the log level through the control plane resource:
see [Change service configuration](04-change-service-configuration.md).

## 6. Verification

You have the right log when it shows the timestamp of the failure you are
investigating. Compare with:

**[READ-ONLY]**

```bash
date -u
oc get pod <pod> -o jsonpath='{.status.startTime}{"\n"}'
```

## 7. Risks and precautions

- `oc logs -f` on several pods and `must-gather` generate load on a small
  single-node cluster; avoid running must-gather during memory pressure.
- must-gather archives contain configuration, including rendered
  configuration files with credentials. Treat the archive as secret and
  never attach it to a public issue unreviewed.
- Debug logging is verbose and logs request details; enable it for a
  limited time.

---
title: "Enable a service"
description: "The lab starts with a minimal set of services."
---

# Enable a service

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

The lab starts with a minimal set of services. Adding one is the equivalent
of setting `enable_horizon: "yes"` in `globals.yml` and running a deploy,
except that there is nothing to run: flipping `enabled` makes the operator
build the whole service. Horizon is the example because it is stateless and
harmless to remove again.

## In short

- Setting `enabled: true` in the control plane resource makes the operator
  build the whole service: no command to run.
- Horizon was `True` about 50 seconds after the patch on the lab, and uses
  about 400 MiB.
- Side effect seen on the lab: the Glance pod is rolled once, when Horizon
  is enabled and when it is disabled.
- Disabling removes the service objects but leaves two TLS Secrets behind.
- Disabling a service that has a database was not executed on this lab.

## 1. Initial symptoms

- You want the dashboard, or want to see what an operator creates for a
  brand-new service.

## 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get oscp openstack -o jsonpath='{.spec.horizon.enabled}{"\n"}'
oc get horizon
oc get pods -l service=horizon
oc get routes
oc get oscp openstack -o json | jq -r '.status.conditions[] | select(.type | test("Horizon"))'
oc adm top node
```

## 3. Expected observations

- `enabled` is `false`; `oc get horizon` and the pod query answer
  `No resources found in openstack namespace.`, no route has "horizon" in
  its name, and there is no Horizon condition on the control plane.
- The node has memory headroom (the Horizon pod uses about 400 MiB).

## 4. Root cause

What enabling does:

1. The openstack operator sees `horizon.enabled: true` and creates a
   `Horizon` resource from the `template` section.
2. The horizon operator generates the configuration (ConfigMaps
   `horizon-config-data` and `horizon-scripts`) and a Secret `horizon`
   holding the Django secret key, then creates a Deployment and a Service,
   both named `horizon`.
3. Because `apiOverride.route` is set, the openstack operator requests two
   certificates (`horizon-svc` for the pod, `horizon-route` for the Route)
   and creates a Route `horizon` (TLS re-encryption, HTTP redirected to
   HTTPS) so that the dashboard is reachable on the `*.apps` domain. It
   reports this as `OpenStackControlPlaneExposeHorizonReady`.

Measured on the lab: the `Horizon` resource exists four seconds after the
patch and is `True` after about 50 seconds, of which 20 are the first pull
of the image. The Glance StatefulSet is rolled once as a side effect, both
when Horizon is enabled and when it is disabled: expect a short Glance API
interruption.

Disabling reverses step 1: the operator deletes the `Horizon` resource, and
Kubernetes garbage collection removes everything it owned (Deployment, pods,
Service, ConfigMaps, the `horizon` Secret) and the Route. The resource is
gone after four seconds, the pod after about thirty. The two Horizon
conditions are removed from the control plane status. Two things stay
behind:

- the TLS Secrets `cert-horizon-route` and `cert-horizon-svc` (the
  `Certificate` resources are removed, their Secrets are not);
- the `template` section under `spec.horizon`, now filled with defaults. It
  is harmless and is reused if you enable the service again.

Horizon has no database. For a service with one (Cinder, Heat, ...) the
operator also creates a database, a database account and a Keystone service
with its endpoints. Disabling such a service was not executed on this lab,
so this guide makes no statement on what it leaves in the database and in
Keystone: check with `oc get mariadbdatabase,mariadbaccount` and
`openstack service list` after doing it.

## 5. Resolution

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '
spec:
  horizon:
    enabled: true
    apiOverride:
      route: {}
    template:
      replicas: 1
      secret: osp-secret
'
```

Watch the operator work:

**[READ-ONLY]**

```bash
oc get horizon -w
oc get pods -l service=horizon -w
oc get events --sort-by=.lastTimestamp | tail -20
```

### Disable again

**[CHANGE]** Removes the dashboard and its generated objects.

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"horizon":{"enabled":false}}}'
```

## 6. Verification

**[READ-ONLY]**

```bash
oc get horizon                                   # STATUS True, "Setup complete"
oc get deployment,pods -l service=horizon
oc get route horizon                             # reencrypt/Redirect
oc get oscp openstack -o json | jq -r '.status.conditions[] | select(.type | test("Horizon")) | "\(.type) \(.status)"'
curl -sk -o /dev/null -w '%{http_code}\n' "https://$(oc get route horizon -o jsonpath='{.spec.host}')/"
```

The `curl` prints `301` (redirect to the login page); add `-L` to follow it
and get `200`.

Log in with user `admin`, domain `Default`, and the admin password
(see [passwords](07-passwords-and-secrets.md)). The dashboard name only
resolves through the lab DNS on the bastion; from a workstation use an SSH
tunnel or a SOCKS proxy through the bastion.

After disabling: `oc get horizon` returns nothing, and the pods, Service and
Route are gone. `oc get secrets | grep horizon` still lists the two `cert-`
Secrets described above; delete them by hand if you want a clean namespace.

## 7. Risks and precautions

- Each enabled service costs memory on a 32 GB node (about 400 MiB for
  Horizon, measured). Check `oc adm top node`
  before and after; see
  [resource exhaustion](../troubleshooting/resource-exhaustion.md).
- Do not enable `telemetry` on OKD without an image override: one of its
  images comes from a registry that requires a Red Hat account, and the pod
  stays in `ImagePullBackOff`.
- Services with their own storage or network needs (Cinder volume backends,
  Swift, Octavia, Designate, Manila) need more than `enabled: true`. Enabling
  them without a backend gives a control plane that never returns to `True`.
- Keep the template in the repository in step with what you enable, or the
  next run of the deployment script will disable it again.

---

**Previous:** [Change service configuration](04-change-service-configuration.md) · **Up:** [Operations guide](index.md) · **Next:** [Scale a service](06-scale-a-service.md)

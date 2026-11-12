# Passwords and secrets

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) except the rotation of database passwords (`DbRootPassword`, `DatabasePassword`, `MariaDBAccount`), not executed because a failure would leave the lab unrecoverable

`passwords.yml` becomes a Kubernetes Secret named `osp-secret`. Services do
not read it directly: each operator copies the keys it needs into the
configuration it renders. This document shows where credentials live and
what was observed when changing one.

## 1. Initial symptoms

- You need the admin password to log in to Horizon or to build a `clouds.yaml`
  for a workstation.
- You wonder which password a service uses for its database or for Keystone.
- You want to rotate a password.

## 2. Read-only investigation

**[READ-ONLY]** (prints secret values on your terminal)

```bash
# Key names only: safe to show.
oc get secret osp-secret -o json | jq -r '.data | keys[]'

# One value.
oc get secret osp-secret -o jsonpath='{.data.AdminPassword}' | base64 -d; echo

# How the OpenStack client pod is configured (it reads the same password).
oc get configmap openstack-config -o jsonpath='{.data.clouds\.yaml}'
oc get secret openstack-config-secret -o json | jq -r '.data | keys[]'

# Database accounts are resources of their own.
oc get mariadbdatabase,mariadbaccount

# Message bus credentials: one generated Secret per consumer.
oc get transporturl
oc get secrets | grep -i transport

# TLS material issued by cert-manager.
oc get issuers,certificates
oc get secret combined-ca-bundle -o json | jq -r '.data | keys[]'

# Which Secret a service resource points to, and which key it reads.
oc get keystoneapi keystone -o jsonpath='{.spec.secret}{"  "}{.spec.passwordSelectors}{"\n"}'
```

## 3. Expected observations

- `osp-secret` holds 23 keys: `AdminPassword`, `DbRootPassword`,
  `DatabasePassword`, `MetadataSecret`, a few encryption keys
  (`BarbicanSimpleCryptoKEK`, `HeatAuthEncryptionKey`) and one
  `<Service>Password` key per service the operators know, enabled or not
  (`NovaPassword`, `NeutronPassword`, `CinderPassword`, ...). The lab
  generates all values randomly at deployment time; they exist nowhere else.
- The ConfigMap `openstack-config` holds a `clouds.yaml` with one cloud named
  `default` and no password; the password is in the Secret
  `openstack-config-secret` (keys `secure.yaml` and `cloudrc`).
- Each service resource names its Secret (`spec.secret: osp-secret`) and the
  key it reads through `passwordSelectors` (for Keystone: `admin:
  AdminPassword`).
- One `MariaDBDatabase` per database (`glance`, `keystone`, `neutron`,
  `nova-api`, `nova-cell0`, `nova-cell1`, `placement`) and one
  `MariaDBAccount` with the same name, plus one root account per Galera
  instance (`openstack-mariadb-root`, `openstack-cell1-mariadb-root`). An
  account names a generated user and a Secret:

  **[READ-ONLY]**

  ```bash
  oc get mariadbaccount placement -o jsonpath='{.spec}{"\n"}'
  ```

  ```text
  {"accountType":"User","requireTLS":false,"secret":"placement-db-secret","userName":"placement_4607"}
  ```

  The suffix of the user name is random. The Secret `<name>-db-secret` has a
  single key, `DatabasePassword`.
- One `TransportURL` per RabbitMQ consumer (`keystone-keystone-transport`,
  `neutron-neutron-transport`, `nova-api-transport`,
  `nova-cell1-transport`), each with a generated Secret
  `rabbitmq-transport-url-<name>` holding the keys `transport_url` and
  `quorumqueues`.
- Five Issuers (`selfsigned-issuer` and the four lab authorities
  `rootca-internal`, `rootca-public`, `rootca-ovn`, `rootca-libvirt`) and 37
  Certificates, all `READY=True`.
- `combined-ca-bundle` holds `tls-ca-bundle.pem` and
  `internal-ca-bundle.pem`.

## 4. Root cause

Three families of credentials, with three owners:

| Credential | Declared in | Consumed through |
|------------|-------------|------------------|
| Keystone admin and service user passwords, database root password, metadata secret | `osp-secret`, created by you | Each operator renders them into its `<service>-config-data` Secret |
| Per-service database users | `MariaDBAccount` resources, managed by the service operators and the mariadb operator | Generated Secrets referenced by the account |
| RabbitMQ users and URLs | `TransportURL` resources, managed by the infra operator | Generated Secrets |
| TLS keys and certificates | `Certificate` resources, managed by cert-manager | `cert-*` Secrets mounted into pods |

Because rendered configuration contains passwords, generated configuration
is stored in Secrets, not ConfigMaps. The hash mechanism of
[04](04-change-service-configuration.md) covers them: when an input Secret
changes, the operator re-renders and rolls the pods.

## 5. Resolution

### Use the admin credentials from the bastion

**[READ-ONLY]** (prints a secret value)

```bash
oc get secret osp-secret -o jsonpath='{.data.AdminPassword}' | base64 -d; echo
oc get route keystone-public -o jsonpath='https://{.spec.host}{"\n"}'
```

For day-to-day work prefer `oc rsh openstackclient`, which needs no copy of
the password.

### Rotate a password

Rotating a Keystone service user password was executed on the lab with
Placement. What happens on this version:

- Changing `PlacementPassword` in `osp-secret` changes an operator input:
  the Placement configuration is re-rendered and its Deployment rolls
  (about 25 seconds). The control plane returns to `True`.
- The operator does **not** change the password of the `placement` user in
  Keystone. The new pod therefore starts with a password Keystone rejects:
  every Placement API request answers HTTP 503 while every condition says
  `True`. Nothing in `oc get openstackcontrolplane` reveals the problem.
- Setting the Keystone user password to the value now in the Secret repairs
  the service at once, without a restart.

A rotation is therefore two changes that must carry the same value. Do them
in this order so that the outage is limited to the rollout:

**[CHANGE]** Interrupts the service until both steps are done. Read the new
password without echo (`read -rs NEW`) so that it stays out of the shell
history. It is still passed as a command argument below, and is therefore
visible in the process list of the bastion while each command runs: do this
on a bastion you do not share, and `unset NEW` afterwards.

```bash
oc rsh openstackclient openstack user set placement --password "${NEW}"
oc patch secret osp-secret --type=merge -p "{\"stringData\":{\"PlacementPassword\":\"${NEW}\"}}"
sleep 30
oc rollout status deployment/placement
oc rsh openstackclient openstack resource provider list
```

Between the first step and the end of the rollout the running pod still
uses the old password and fails: measured twice on the lab, the Placement
API answered HTTP 503 for about 20 seconds, then worked again. The `sleep`
is there because `oc rollout status` run immediately after the patch
returns "successfully rolled out" about the old pod, before the operator
has changed the Deployment. To go back, repeat both steps with the previous
value.

Not executed on this lab, and to be treated as a planned change with a
rebuild as the fallback:

- `DbRootPassword` and `DatabasePassword`. A mismatch between the Secret and
  the database locks the operators out of Galera.
- Database account rotation. It is designed around `MariaDBAccount`: create
  a new account, point the service at it, remove the old one.
- `AdminPassword`. The same two-step logic applies (Keystone user `admin`
  and the Secret), but every operator uses that password, so a mismatch
  stops all reconciliation that talks to Keystone.

TLS certificates are renewed by cert-manager on its own before expiry; the
new Secret changes the hash and rolls the pods.

## 6. Verification

After any credential-related change:

**[READ-ONLY]**

```bash
oc get openstackcontrolplane openstack
oc rsh openstackclient openstack token issue
oc rsh openstackclient openstack compute service list
oc rsh openstackclient openstack network agent list
oc logs -l service=nova-api --all-containers --since=5m | grep -ci 'unauthorized\|401' || true
oc rsh openstackclient openstack resource provider list   # Placement really answers
```

Conditions are not enough after a password change: call the API of the
service whose password you changed.

## 7. Risks and precautions

- `oc get secret -o yaml` prints base64, which is an encoding, not
  encryption. Do not paste it into tickets or chat. Clear your terminal
  scrollback after printing a password.
- Anyone who can read Secrets in the `openstack` namespace has every
  OpenStack credential. Access to the namespace is access to the cloud.
- Never commit an exported Secret to Git. The repository generates
  `osp-secret` in the cluster precisely so that no file holds it.
- Do not delete `osp-secret`. Operators would report `InputReady=False`, and
  recreating it with new random values desynchronises every service from
  Keystone and the databases.
- Do not edit generated Secrets (`*-config-data`, transport URL Secrets,
  `cert-*`): they are rewritten.
- Compute nodes receive credentials through Ansible. A change that affects
  `nova-compute` or the OVN agents needs a new data plane deployment
  ([08](08-dataplane-changes.md)).

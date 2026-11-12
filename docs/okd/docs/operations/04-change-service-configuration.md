# Change service configuration

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

In Kolla-Ansible you drop an override in `/etc/kolla/config/<service>/` and
run `kolla-ansible reconfigure`. Here the override lives in the
`OpenStackControlPlane` resource (`customServiceConfig`) and there is no
"reconfigure" command: saving the resource **is** the trigger. The example
enables debug logging in Keystone.

## 1. Initial symptoms

- You need to set or change an option in a service configuration file.
- You changed a ConfigMap or Secret by hand and the change vanished.

## 2. Read-only investigation

Where is the configuration today?

**[READ-ONLY]**

```bash
# What you declared (empty if never set):
oc get oscp openstack -o jsonpath='{.spec.keystone.template.customServiceConfig}{"\n"}'

# What the operator generated from it (a Secret, because it holds passwords):
oc get secret keystone-config-data -o json | jq -r '.data | keys[]'
oc get secret keystone-config-data -o jsonpath='{.data.custom\.conf}' | base64 -d

# What the running process actually reads:
oc exec deployment/keystone -- ls /etc/keystone/keystone.conf.d/
oc exec deployment/keystone -- cat /etc/keystone/keystone.conf.d/custom.conf

# The fingerprint of the current configuration, as seen by the pod:
oc get deployment keystone -o json | jq -r '.spec.template.spec.containers[0].env[] | select(.name == "CONFIG_HASH")'
oc get pods -l service=keystone
```

Note the pod name and the `CONFIG_HASH` value: both must change.

## 3. Expected observations

- `customServiceConfig` is empty for Keystone in the lab manifest. Glance
  and Neutron have one; look at them for a real example:

  **[READ-ONLY]**

  ```bash
  oc get oscp openstack -o jsonpath='{.spec.neutron.template.customServiceConfig}'
  ```

  ```text
  [DEFAULT]
  global_physnet_mtu = 1442
  [ml2]
  path_mtu = 1442
  ```

- The Secret `keystone-config-data` holds the keys `keystone.conf`,
  `custom.conf`, `httpd.conf`, `ssl.conf`, `my.cnf`,
  `keystone-api-config.json` and `TemplateParameters`. Its `custom.conf` is
  empty.
- `/etc/keystone/keystone.conf.d/` contains a single file, `custom.conf`.
  The main file is `/etc/keystone/keystone.conf`; files of the `.d`
  directory are read after it, so `custom.conf` wins over generated values.
- The `CONFIG_HASH` environment variable is a hash of all configuration
  inputs.

## 4. Root cause

The mechanism, step by step:

1. You change `spec.keystone.template.customServiceConfig` on
   `OpenStackControlPlane/openstack`.
2. The openstack operator copies the Keystone section into
   `KeystoneAPI/keystone`.
3. The keystone operator re-renders the Secret `keystone-config-data` and
   recomputes the hash of its inputs.
4. The new hash is written into the pod template as `CONFIG_HASH`. A pod
   template change is what makes a Deployment roll: a new pod starts, and the
   old one is removed once the new one is ready.

So the rollout is a side effect of the hash, and the hash is a side effect
of your edit. Nothing restarts if the rendered configuration is identical.

The operator does **not** validate the content: it is pasted into the file
as is. An option in the wrong section is silently ignored by the service; a
value the service cannot parse makes the new pod crash
(see [CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md)).

Why hand edits do not stick: the Secret and the `KeystoneAPI` resource are
outputs. The operator rewrites them from the level above on every
reconciliation (see
[manual changes reverted](../troubleshooting/manual-changes-reverted.md)).

For Nova the generated override file is named `02-nova-override.conf`
instead of `custom.conf` (mounted as
`/etc/nova/nova.conf.d/02-nova-override.conf`); the key only exists in the
Secret `nova-api-config-data` while a `customServiceConfig` is set. The
mechanism is identical.

Measured on the lab with the Keystone example below: `KeystoneAPI/keystone`
and the control plane resource report `False`, "Deployment in progress", for
about 35 seconds, then `True`. Reverting gives back the original
`CONFIG_HASH` value, and the Deployment reuses its original ReplicaSet: the
same input always renders the same hash.

## 5. Resolution

Save the current state first, so that you can go back:

**[READ-ONLY]**

```bash
oc get oscp openstack -o yaml > /tmp/oscp-before.yaml
```

Apply the change. `oc patch` is repeatable and reviewable; `oc edit
openstackcontrolplane openstack` does the same interactively.

**[CHANGE]** Rolls the Keystone pod: brief interruption of authentication
with one replica.

```bash
oc patch openstackcontrolplane openstack --type=merge -p '
spec:
  keystone:
    template:
      customServiceConfig: |
        [DEFAULT]
        debug = true
'
```

Watch it propagate:

**[READ-ONLY]**

```bash
oc get keystoneapi keystone -w                 # False (in progress) then True
oc rollout status deployment/keystone
oc get pods -l service=keystone
```

To keep the change across a rebuild of the lab, also put it in
`deployment/openstack/controlplane/openstackcontrolplane.yaml.tmpl`.
Otherwise the next run of `scripts/bastion/06-openstack-controlplane.sh`
re-applies the file and removes your option.

### Revert

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"keystone":{"template":{"customServiceConfig":""}}}}'
```

## 6. Verification

**[READ-ONLY]**

```bash
# New pod, new hash:
oc get pods -l service=keystone
oc get deployment keystone -o json | jq -r '.spec.template.spec.containers[0].env[] | select(.name == "CONFIG_HASH")'

# The file inside the running pod:
oc exec deployment/keystone -- cat /etc/keystone/keystone.conf.d/custom.conf

# The effect:
oc rsh openstackclient openstack token issue
oc logs deployment/keystone --since=2m | grep -c DEBUG   # 0 before; more than 1000 after two minutes

# Control plane back to Ready:
oc get openstackcontrolplane openstack
```

## 7. Risks and precautions

- Every configuration change restarts the service. With one replica that is
  a short outage; plan it like a restart.
- A wrong value can stop the new pod from starting. For a Deployment the old
  pod keeps serving until the new one is ready, so a bad change to Keystone,
  Neutron or Placement usually degrades nothing but never completes. For a
  StatefulSet with one replica (every Nova service, Glance) the old pod is
  stopped first: a bad change is an outage until you revert. Observed on the
  lab with an unparsable boolean in the Nova API configuration: the new pod
  stayed `0/2 Running`, the API answered 503, and the revert brought it back
  in about 25 seconds.
- Change one service at a time and wait for `True` before the next.
- `--type=merge` replaces the whole `customServiceConfig` string. Include the
  existing content when a service already has one (Glance, Neutron).
- Do not put passwords in `customServiceConfig`: the resource is readable by
  anyone who can read the namespace. On this version Glance and the Cinder
  back-end services accept `customServiceConfigSecrets` (a list of Secret
  names whose content is added to the configuration); Keystone, Neutron,
  Placement and the Nova services do not have that field
  (`oc explain openstackcontrolplane.spec.glance.template` shows what a
  service accepts).
- Some services already log at debug level by default (Nova does), so
  `debug = true` changes nothing visible there. Keystone is the example
  because the difference is obvious.
- Changes for `nova-compute` on compute nodes do not go through this path:
  see [data plane changes](08-dataplane-changes.md).

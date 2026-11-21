---
title: "OpenStack identity and tenants"
description: "Day-1 tenant work on an operator-managed cloud: where the admin client lives, how to reach the API as a normal user, and what to create for a new team."
---

# OpenStack identity and tenants

> Status: every command was run on the lab (OKD 4.22, operators 18-stable,
> OpenStack 2023.1 Antelope, one KVM compute node) on 2026-11-12

## In short

- The admin client is the `openstackclient` pod (`oc exec`); nothing is
  written on the bastion.
- From outside the cluster use the public Routes on 443 with the
  exported CA (`rootca-public`, key `ca.crt`); the internal endpoints
  only work from pods.
- Domains, projects, users, quotas, flavors and images are plain
  OpenStack objects: no custom resource describes them, and the database
  backup is their only copy.
- `reader` and `member` are enforced strictly (secure RBAC is on).
- Glance stores images as files on a local volume of the node, whose
  10Gi size is not enforced.

Day-1 tenant work on an operator-managed cloud: where the admin client
lives, how to reach the API as a normal user, and what to create for a new
team. Commands run on the bastion in the `openstack` namespace
(`oc project openstack`) unless stated otherwise.

## Entries

### Where is the admin client and which credentials does it use?

**Context**: Kolla-Ansible writes `/etc/kolla/admin-openrc.sh` on the
deployment host. Here nothing is written to the bastion: the admin client is
a pod.

**How**:

**[READ-ONLY]**

```bash
oc exec openstackclient -c openstackclient -- openstack token issue -f value -c expires
oc exec openstackclient -c openstackclient -- bash -c 'ls ~/.config/openstack/ ~/cloudrc; grep -E "auth_url|interface|cloud" ~/.config/openstack/clouds.yaml'
oc get configmap openstack-config -o jsonpath='{.data.clouds\.yaml}'
oc get secret openstack-config-secret -o json | jq -r '.data | keys[]'
```

**Observed on the lab** (2026-11-12):

```text
/home/cloud-admin/cloudrc
/home/cloud-admin/.config/openstack/:
clouds.yaml  secure.yaml
      auth_url: https://keystone-public-openstack.apps.okd.lab.example.com
```

The cloud is named `default`. `clouds.yaml` comes from the ConfigMap
`openstack-config`, `secure.yaml` and `cloudrc` from the Secret
`openstack-config-secret`; both are owned by the `KeystoneAPI` resource.
A token lives one hour.

**Why / how it works**: the Keystone operator renders the client
configuration and the `OpenStackClient` resource mounts it in a pod that
also trusts the lab certificate authorities. Kolla-Ansible equivalent:
`source /etc/kolla/admin-openrc.sh`.

**Pitfalls**:

- The pod uses the **public** endpoint (the OKD Route), not the internal
  one. If the Route or the ingress router is down, the admin client is down
  too, even though the services still talk to each other.
- Do not `cat` `secure.yaml` or `cloudrc` in a shared terminal: they hold
  the admin password.
- `oc rsh openstackclient` gives an interactive shell; in scripts prefer
  `oc exec openstackclient -c openstackclient -- openstack ...`.

**See also**: [Inspect service status](../operations/01-inspect-service-status.md),
[Passwords and secrets](../operations/07-passwords-and-secrets.md),
[Configuration, secrets and data](../concepts/04-configuration-secrets-and-data.md)

### Which endpoint do I use from where: public Route or internal service?

**Context**: every service registers two endpoints. A user outside the
cluster and a pod inside it do not use the same one.

**How**:

**[READ-ONLY]**

```bash
oc exec openstackclient -c openstackclient -- openstack endpoint list -c "Service Name" -c Interface -c URL
oc get route -n openstack
# From the bastion:
curl -s -o /dev/null -w '%{http_code}\n' --cacert ~/kb-demo/rootca-public.crt https://keystone-public-openstack.apps.okd.lab.example.com/v3
getent hosts keystone-internal.openstack.svc || echo "internal name does not resolve here"
# From a pod:
oc exec openstackclient -c openstackclient -- curl -s -o /dev/null -w '%{http_code}\n' https://keystone-internal.openstack.svc:5000/v3
```

**Observed on the lab** (2026-11-12):

```text
keystone   internal  https://keystone-internal.openstack.svc:5000
keystone   public    https://keystone-public-openstack.apps.okd.lab.example.com
nova       internal  https://nova-internal.openstack.svc:8774/v2.1
nova       public    https://nova-public-openstack.apps.okd.lab.example.com/v2.1
```

From the bastion the public URL answers `200`; the internal name does not
resolve and the internal load-balancer address (172.17.0.80, network
`internalapi`) times out. From a pod the internal URL answers `200`.

**Why / how it works**: public endpoints are OKD Routes on port 443
(TLS re-encrypted by the router); internal endpoints are Kubernetes Services
of type LoadBalancer on the isolated `internalapi` network. Kolla-Ansible
equivalent: `kolla_external_vip_address` versus `kolla_internal_vip_address`.

**Pitfalls**:

- There is no `admin` interface in the catalogue, only `public` and
  `internal`. Old scripts using `--os-interface admin` fail.
- Public URLs have no port number; internal URLs keep the classic ports
  (5000, 8774, 9292, 9696, 8778).
- A client outside the cluster needs DNS for
  `*.apps.okd.lab.example.com`; the bastion provides it on the lab.

**See also**: [Architecture](../architecture.md),
[DNS and routing](../troubleshooting/dns-and-routing.md),
[From Kolla to operators](../concepts/01-from-kolla-to-operators.md)

### Where is the TLS certificate authority and how do I export it?

**Context**: all API endpoints use TLS with certificates issued inside the
cluster. A client outside the cluster refuses them until it trusts the lab
root CA.

**How**:

**[READ-ONLY]**

```bash
oc get issuer -n openstack
oc get secret rootca-public -n openstack -o jsonpath='{.data.ca\.crt}' | base64 -d > ~/kb-demo/rootca-public.crt
openssl x509 -in ~/kb-demo/rootca-public.crt -noout -subject -enddate
oc get secret combined-ca-bundle -n openstack -o json | jq -r '.data | keys[]'
curl -s -o /dev/null -w '%{http_code}\n' https://keystone-public-openstack.apps.okd.lab.example.com/v3 || echo "refused without the CA"
```

**Observed on the lab** (2026-11-12):

```text
subject=CN = rootca-public
internal-ca-bundle.pem
tls-ca-bundle.pem
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

Four CA issuers exist (`rootca-public`, `rootca-internal`, `rootca-libvirt`
and `rootca-ovn`) next to the `selfsigned-issuer` that signed them. The
public root is valid ten years; the certificate on a Route is valid five
years and names only the Route host. The Secret
`combined-ca-bundle` (system CAs plus the four lab roots, 122 certificates)
is what every service pod and the client pod mount.

**Why / how it works**: cert-manager issues every certificate from
self-signed roots stored as Secrets; the OpenStack operator assembles the
bundle. Kolla-Ansible equivalent: `kolla-ansible certificates` and
`/etc/kolla/certificates/ca/root.crt`.

**Pitfalls**:

- Export `ca.crt`, never `tls.key`: the same Secret holds the private key
  of the root CA.
- `--insecure` hides the problem and trains bad habits; give users the CA
  file with their `clouds.yaml`.
- Internal endpoints are signed by `rootca-internal`, not by the public
  root: a client inside the cluster needs the bundle, not only the public
  root.

**See also**: [Passwords and secrets](../operations/07-passwords-and-secrets.md),
[Platform services](../installation/03-platform-services.md)

### How do I create a domain, a project and users for a new team?

**Context**: first request from a new team. The API is plain Keystone; only
the place you run the client from changes.

**How**:

**[CHANGE]** Creates identity objects; nothing else is touched.

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
os domain create --description "Knowledge base demo" kb-demo
os project create --domain kb-demo kb-demo
# Password read from a file (mode 600) so that it never reaches the terminal:
os user create --domain kb-demo --project kb-demo --project-domain kb-demo \
  --password "$(cat ~/kb-demo/password)" kb-demo-member
os user create --domain kb-demo --password "$(cat ~/kb-demo/password)" kb-demo-reader
os role add --user kb-demo-member --user-domain kb-demo --project kb-demo --project-domain kb-demo member
os role add --user kb-demo-reader --user-domain kb-demo --project kb-demo --project-domain kb-demo reader
```

**[READ-ONLY]**

```bash
os role list -f value -c Name
os role assignment list --project kb-demo --project-domain kb-demo --names -f value
```

**Observed on the lab** (2026-11-12):

```text
admin
member
reader
service
member kb-demo-member@kb-demo  kb-demo@kb-demo   False
reader kb-demo-reader@kb-demo  kb-demo@kb-demo   False
```

**Why / how it works**: Keystone is bootstrapped by its operator with the
default roles, and the services run with `enforce_new_defaults = true` and
`enforce_scope = true`, so `reader` really is read-only and `member` cannot
call admin APIs. Kolla-Ansible equivalent: the same `openstack` commands
after `source admin-openrc.sh`.

**Pitfalls**:

- These objects live only in the Keystone database. No custom resource
  describes them, so the operators neither recreate nor remove them; the
  database backup is their only copy.
- A password given on the command line is visible in the process list of
  the client pod for a moment; on a shared cluster use `--password-prompt`
  from `oc rsh`.
- The domain name must be repeated in almost every command
  (`--user-domain`, `--project-domain`) as soon as you leave `Default`.

**See also**: [Backup and restore](../lifecycle/05-backup-and-restore.md),
[Passwords and secrets](../operations/07-passwords-and-secrets.md)

### How do I set and check the quotas of a project?

**Context**: default quotas are generous; a small lab or a new team needs
tighter ones for compute and network.

**How**:

**[READ-ONLY]**

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
p=$(os project show kb-demo --domain kb-demo -f value -c id)
os quota show "$p"
os quota show --usage "$p"
```

**[CHANGE]**

```bash
os quota set --instances 4 --cores 4 --ram 2048 --key-pairs 5 --server-groups 2 "$p"
os quota set --networks 3 --subnets 3 --routers 1 --floating-ips 3 --ports 20 \
  --secgroups 5 --secgroup-rules 30 "$p"
```

**Observed on the lab** (2026-11-12): defaults were 10 instances, 20 cores,
51200 MB, 100 networks, 500 ports, 10 routers and 50 floating IPs. After
the change, with the demo networks in place:

```text
cores 4 0 0
instances 4 0 0
ram 2048 0 0
networks 3 1 0
ports 20 2 0
routers 1 1 0
```

**Why / how it works**: one client command, two back ends: Nova stores
compute quotas in its API database, Neutron stores network quotas in its
own. Kolla-Ansible equivalent: identical commands.

**Pitfalls**:

- Give the project **ID** when the project is outside the `Default` domain;
  a name is looked up in the admin's domain.
- `openstack quota list --detail` is deprecated in this client;
  `quota show --usage` replaces it.
- The network part prints a warning about a future `--force` default; it is
  only a notice.
- The metadata port of each network counts against the `ports` quota of
  the project (two ports are used here with no instance).

**See also**: [Capacity and observability](openstack-capacity-and-observability.md)

### How does a non-admin user get a working CLI?

**Context**: the client pod is the admin's tool. A project member needs a
client on their own machine, a `clouds.yaml`, and the CA.

**How**:

**[CHANGE]** Installs a client in a virtual environment on the bastion
(through the lab proxy).

```bash
python3 -m venv ~/kb-demo/venv
~/kb-demo/venv/bin/pip install python-openstackclient osc-placement
```

**[CHANGE]** Writes the client configuration; the password is read from a
file and never typed on the command line.

```bash
umask 077
cat > ~/kb-demo/clouds.yaml <<YAML
clouds:
  kb-demo:
    auth:
      auth_url: https://keystone-public-openstack.apps.okd.lab.example.com
      username: kb-demo-member
      password: "$(cat ~/kb-demo/password)"
      project_name: kb-demo
      user_domain_name: kb-demo
      project_domain_name: kb-demo
    region_name: regionOne
    interface: public
    identity_api_version: 3
    cacert: $HOME/kb-demo/rootca-public.crt
YAML
```

**[READ-ONLY]**

```bash
export OS_CLIENT_CONFIG_FILE=~/kb-demo/clouds.yaml OS_CLOUD=kb-demo
~/kb-demo/venv/bin/openstack token issue -f value -c project_id -c expires
~/kb-demo/venv/bin/openstack catalog list -f value -c Name -c Type
~/kb-demo/venv/bin/openstack user list
```

**Observed on the lab** (2026-11-12): the installation took 18 s
(client 6.2.1). The token and the catalogue are returned; `user list`
answers `You are not authorized to perform the requested action:
identity:list_users. (HTTP 403)`, as do `flavor create`, `hypervisor list`
and `image set --public`.

**Why / how it works**: nothing is specific to the operators once the user
has the public URL and the CA; the region is `regionOne`. Kolla-Ansible
equivalent: a per-user openrc pointing at the external VIP.

**Pitfalls**:

- The bastion has no `openstack` command by default; without the virtual
  environment you only have the admin pod.
- Running as another user **inside** the admin pod works only if you
  neutralise its cloud first:
  `oc exec openstackclient -c openstackclient -- env OS_CLOUD= OS_AUTH_URL=... OS_USERNAME=... openstack ...`;
  otherwise the admin `clouds.yaml` wins silently.
- `interface: public` is required outside the cluster; with `internal` the
  client hangs on names it cannot resolve.

**See also**: [Verification](../installation/07-verification.md),
[DNS and routing](../troubleshooting/dns-and-routing.md)

### How do I add flavors, an image, a keypair and a security group?

**Context**: the cloud is empty after installation: no flavor, no image, no
external network.

**How**:

**[CHANGE]** Admin side: flavors and a public image. The image is piped
through `oc exec -i` because the file is on the bastion, not in the pod.

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
os flavor create --vcpus 1 --ram 256 --disk 1 kb.tiny
os flavor create --vcpus 1 --ram 512 --disk 2 kb.small
oc exec -i openstackclient -c openstackclient -- openstack image create kb-cirros-0.6.3 \
  --public --disk-format qcow2 --container-format bare < ~/kb-demo/cirros.img
```

**[CHANGE]** Member side, with the user's own client.

```bash
o=~/kb-demo/venv/bin/openstack
ssh-keygen -t ed25519 -N '' -f ~/kb-demo/id_kb
$o keypair create --public-key ~/kb-demo/id_kb.pub kb-demo-key
$o security group create kb-demo-ssh
$o security group rule create --proto icmp kb-demo-ssh
$o security group rule create --proto tcp --dst-port 22 kb-demo-ssh
```

**Observed on the lab** (2026-11-12): the 21 MB CirrOS image was uploaded
in 6.4 s and became `active`; `image show` reports `visibility public`,
`disk_format qcow2`.

**Why / how it works**: with no file given, `image create` reads the image
from standard input, which `oc exec -i` forwards into the pod.
Kolla-Ansible equivalent: `openstack image create --file` on the deployment
host, or `init-runonce`.

**Pitfalls**:

- `--file /path` refers to a path **inside the client pod**; a bastion path
  fails with "file not found". Pipe the file or download it from inside the
  pod.
- The lab has no direct Internet access from pods; downloads need the proxy
  (the smoke test uses `HTTP_PROXY_URL` for this).
- Only an admin may publish an image (`--public`); a member can upload a
  private one.
- A keypair belongs to a **user**, not to a project: another member of the
  project does not see it.

**See also**: [Verification](../installation/07-verification.md),
[Compute operations](openstack-compute.md)

### Where does Glance store an uploaded image on the node?

**Context**: you need to know what a backup must contain, or why the node
disk fills up.

**How**:

**[READ-ONLY]**

```bash
oc exec glance-default-single-0 -c glance-httpd -- ls -la /var/lib/glance/images/
oc get pvc glance-glance-default-single-0 -o jsonpath='{.spec.volumeName} {.status.capacity.storage}{"\n"}'
oc get pv "$(oc get pvc glance-glance-default-single-0 -o jsonpath='{.spec.volumeName}')" -o jsonpath='{.spec.local.path}{"\n"}'
oc exec glance-default-single-0 -c glance-httpd -- df -h /var/lib/glance
```

**Observed on the lab** (2026-11-12):

```text
-rw-r--r--. 1 glance glance 21692416 Nov 12 06:42 <image-id>
local-storage-01 10Gi
/var/lib/openstack-lab-pv/pv01
/dev/vda4       150G   45G  106G  30% /var/lib/glance
```

One file per image, named by the image ID, in the `images/` directory of
the local volume, that is `/var/lib/openstack-lab-pv/pv01/images/<image-id>`
on the OKD node.

**Why / how it works**: Glance uses the `file` store on a PersistentVolume
of the `local-storage` class, which is a plain directory of the node.
Kolla-Ansible equivalent: `/var/lib/glance/images` on the controller
(`glance_backend_file`).

**Pitfalls**:

- The 10Gi size of the claim is **not enforced**: `df` shows the whole node
  file system. Images can fill the disk shared with etcd and the databases.
- The pod has two containers, `glance-log` and `glance-httpd`; there is no
  container named `glance-api`.
- With a local volume the images exist on one node only: they are not part
  of the database backup.

**See also**: [Storage](../troubleshooting/storage.md),
[Backup and restore](../lifecycle/05-backup-and-restore.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

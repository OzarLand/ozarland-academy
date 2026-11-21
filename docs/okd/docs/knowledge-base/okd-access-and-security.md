---
title: "OKD access, users and security"
description: "OKD access, users and security"
---

# OKD access, users and security

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- The bastion works as `system:admin` with a 10-year client certificate
  that cannot be revoked and carries no personal identity. Keep it as
  break-glass access and give named accounts instead.
- Named users: an htpasswd identity provider plus role bindings. To
  remove one, delete bindings first, then tokens, then User and
  Identity.
- A read-only user sees health, pods, logs and events, but no Secret and
  no shell. Two surprises: Route TLS private keys are readable, and the
  OpenStack custom resources are not until a ClusterRole is added.
- The operators hold cluster-wide rights on Secrets; the service pods
  hold almost none.
- The audit log says when and from where, keeps about 10 hours, and
  records no request body.

Who can do what on the cluster that carries the OpenStack control plane:
the credentials the bastion uses, how to give a colleague a named
account (administrator or read-only), what a read-only account really
sees, the permissions the OpenStack operators ship, the security
contexts of the OpenStack pods, and how to find who changed something.
OpenStack's own users and policies (Keystone) are a different subject,
see [OpenStack identity](openstack-identity-and-tenants.md). Commands run
on the bastion as the cluster administrator.

## Entries

### Which credentials does the bastion use, and when do they expire?

**Context**: before sharing access, or when `oc` suddenly answers
`Unauthorized`.

**How**:

**[READ-ONLY]**

```bash
oc whoami; oc whoami --show-server; oc config get-contexts
echo "KUBECONFIG=${KUBECONFIG:-unset (so ~/.kube/config)}"; ls -l ~/.kube/config
oc config view --raw -o jsonpath='{.users[0].user.client-certificate-data}' | base64 -d \
  | openssl x509 -noout -subject -issuer -dates
ls .work/okd/install/auth/
oc get secret -n kube-system kubeadmin -o jsonpath='{.metadata.creationTimestamp}{"\n"}'
oc get oauth cluster -o jsonpath='{.spec}{"\n"}'; oc get users; oc get identities
oc get clusterrolebinding cluster-admin cluster-admins -o wide
```

**Observed on the lab** (2026-11-12):

```text
system:admin
https://api.okd.lab.example.com:6443
KUBECONFIG=unset (so ~/.kube/config)
-rw-------. 1 cloud-user cloud-user ... /home/cloud-user/.kube/config
subject=O=system:masters, CN=system:admin
issuer=OU=openshift, CN=admin-kubeconfig-signer
notBefore=Nov 11 19:08:23 2026 GMT
notAfter=Nov  8 19:10:58 2036 GMT
kubeadmin-password  kubeconfig
2026-11-11T19:36:41Z                    # the kubeadmin secret exists
{}                                      # no identity provider configured
No resources found                      # no User, no Identity
cluster-admin    ClusterRole/cluster-admin   ... system:masters
cluster-admins   ClusterRole/cluster-admin   ... system:cluster-admins, system:admin
```

Two administrator credentials exist after installation:

| Credential | What it is | Lifetime | Used by |
|---|---|---|---|
| `system:admin` | client certificate inside the installer's kubeconfig, group `system:masters` | 10 years | every `oc` command of the bastion and of the lab scripts |
| `kubeadmin` | password (file `auth/kubeadmin-password`), checked by the OAuth server against a hash in Secret `kube-system/kubeadmin` | until the Secret is deleted | web console, `oc login -u kubeadmin` |

**Why / how it works**: the API server accepts several authentication
methods in parallel. A client certificate signed by
`admin-kubeconfig-signer` is accepted directly by the API server, with
the user and group read from the certificate subject; it does not depend
on the OAuth server, on the ingress router or on any pod. The group
`system:masters` bypasses RBAC entirely. Passwords and tokens go through
the `oauth-openshift` pod. Kolla-Ansible equivalent: SSH access as the
deployment user plus `passwords.yml`; there is no API-level identity
there.

**Pitfalls**:

- The certificate kubeconfig cannot be revoked individually and carries
  no personal identity: every action appears as `system:admin` in the
  audit log, whoever typed it (all of the morning's changes on this lab
  do). Copying this file to a colleague gives them irrevocable full
  access for 10 years. Give named accounts instead (next entries).
- It is also the only credential that still works when the
  authentication operator, the router or the OAuth pod is broken. Keep
  it, protected (mode 600), as the break-glass access.
- Deleting the `kubeadmin` Secret is permanent (it cannot be recreated
  with a new password by a supported method). Do it only after another
  cluster-admin account works.
- `oc login` rewrites the current kubeconfig. Use
  `--kubeconfig=<other file>` for any second identity so that the
  bastion's `system:admin` context is never replaced.

**See also**: [Certificates inventory](okd-cluster-health-and-etcd.md#which-certificates-does-the-platform-use-when-do-they-expire-and-which-rotate-by-themselves),
[OKD installation](../installation/02-okd.md)

### How do I add named users (a second administrator, a read-only user)?

**Context**: a colleague joins operations; they need their own account
so that their actions are attributable and their access revocable.

**How**:

**[CHANGE]** — rolls the OAuth server pod (about 30 seconds without
password/token logins; existing sessions and the certificate kubeconfig
are not affected). No node reboot, no API server restart.

```bash
set -euo pipefail; umask 077
mkdir -p .work/idp
# 1. password file (no htpasswd binary on the bastion: openssl produces the same format)
for u in ops-admin ops-viewer; do
  openssl rand -hex 12 > .work/idp/$u.pass
  echo "$u:$(openssl passwd -apr1 -stdin < .work/idp/$u.pass)" >> .work/idp/htpasswd
done
# 2. Secret + identity provider
oc create secret generic local-htpasswd -n openshift-config --from-file=htpasswd=.work/idp/htpasswd
oc patch oauth cluster --type merge -p '{"spec":{"identityProviders":[
  {"name":"local","mappingMethod":"claim","type":"HTPasswd","htpasswd":{"fileData":{"name":"local-htpasswd"}}}]}}'
# 3. wait for the new OAuth pod
oc get co authentication; oc get pods -n openshift-authentication
# 4. roles (can be given before the first login)
oc adm policy add-cluster-role-to-user cluster-admin ops-admin
oc adm policy add-cluster-role-to-user cluster-reader ops-viewer
oc adm policy add-role-to-user view ops-viewer -n openstack
# 5. first login, in a separate kubeconfig
oc login --kubeconfig=.work/idp/viewer.kubeconfig --insecure-skip-tls-verify \
  -u ops-viewer -p "$(cat .work/idp/ops-viewer.pass)" https://api.okd.lab.example.com:6443
oc --kubeconfig=.work/idp/viewer.kubeconfig whoami
```

To add or change a user later: edit the htpasswd file and
`oc set data secret/local-htpasswd -n openshift-config --from-file=htpasswd=...`
(the OAuth pod reloads the file; not exercised on the lab).

**Observed on the lab** (2026-11-12), with throwaway users, removed
afterwards:

```text
12:11:01 secret created, oauth patched
12:11:56 authentication  Available=True  Progressing=False     # nothing visible for about one minute
12:12:07 authentication  Available=False Progressing=True      # old pod Terminating, new one Pending
12:12:39 authentication  Available=True  Progressing=True      # new pod Running
NAME         UID      FULL NAME   IDENTITIES                   # objects created by the first login
<admin>      <uuid>               local:<admin>
<viewer>     <uuid>               local:<viewer>
USER       CLIENT                         EXPIRES              # oc get oauthaccesstokens
<viewer>   openshift-challenging-client   86400
Error from server (Forbidden): nodes is forbidden: User "<admin>" cannot list resource "nodes" ...   # before step 4
```

**Why / how it works**: the OAuth server checks the password against
the htpasswd Secret, creates a `User` and an `Identity` object at the
first login, and returns a token valid 24 hours (stored as an
`OAuthAccessToken`). A user has no permission at all until a binding
names them. `cluster-reader` gives read access to most resources of
every namespace and to cluster-scoped objects; `view` adds the
namespace's readable objects. Other provider types (LDAP, OpenID
Connect) plug in the same way. Kolla-Ansible equivalent: adding a Unix
account with or without sudo on the controllers.

**Pitfalls**:

- With one OAuth replica on one node, the pod is stopped before its
  replacement starts: about 30 seconds during which `oc login` and the
  console login fail (`authentication` reports `Available=False`). The
  operator waits about one minute before starting the rollout; do not
  conclude that nothing happens.
- `--certificate-authority` with the API CA taken from the kubeconfig
  worked for `oc login`; `--insecure-skip-tls-verify` also works and is
  what a colleague's laptop will need unless it trusts the lab CAs.
- A token lasts 24 hours: named users must log in again every day; a
  script must not depend on such a token (use a ServiceAccount).
- `add-cluster-role-to-user cluster-admin` creates a binding with a
  generated name (`cluster-admin-0`): search bindings by subject, not by
  name, when auditing.
- The htpasswd Secret holds only hashes, but the password files in
  `.work/` are plain text: hand them over and delete them.

**See also**:
[Passwords and secrets](../operations/07-passwords-and-secrets.md)

### What can a read-only user really see?

**Context**: deciding whether `cluster-reader` + `view` is safe to give
to someone who must not get the OpenStack passwords.

**How**:

**[READ-ONLY]** — run as the read-only user (`V` is its kubeconfig).

```bash
V=.work/idp/viewer.kubeconfig
oc --kubeconfig=$V get nodes; oc --kubeconfig=$V get co; oc --kubeconfig=$V adm top node
oc --kubeconfig=$V get pods,cm,events,pvc -n openstack; oc --kubeconfig=$V get pv
oc --kubeconfig=$V logs -n openstack deploy/keystone -c keystone-api --tail=1
oc --kubeconfig=$V get secrets -n openstack
oc --kubeconfig=$V exec -n openstack openstackclient -- openstack token issue
oc --kubeconfig=$V debug node/okd-0 -- true
oc --kubeconfig=$V adm node-logs okd-0 --path=kube-apiserver/audit.log
oc --kubeconfig=$V get openstackcontrolplane -n openstack
oc --kubeconfig=$V get machineconfig
oc --kubeconfig=$V get route -n openstack keystone-public -o jsonpath='{.spec.tls.key}' | head -c 27
for q in "get secrets" "get pods/log" "create pods/exec" "create pods/portforward" "get configmaps"; do
  printf '%-26s %s\n' "$q" "$(oc --kubeconfig=$V auth can-i $q -n openstack)"; done
```

**Observed on the lab** (2026-11-12):

| Action | Result |
|---|---|
| nodes, cluster operators, `adm top`, PVs, events, pods, ConfigMaps | allowed |
| pod logs (`oc logs`) | allowed |
| Secrets (list or get, any namespace) | **Forbidden** |
| `oc exec`, `oc rsh`, port-forward, `oc debug node` | **Forbidden** (cannot create `pods/exec`, cannot create pods) |
| node logs, audit log (`nodes/proxy`) | **Forbidden** |
| delete, patch, annotate anything | **Forbidden** |
| MachineConfigs | **Forbidden** (they can contain files with credentials) |
| OpenStack custom resources (OpenStackControlPlane, KeystoneAPI, Galera, node sets...) | **Forbidden** — the operators ship no read role |
| Route `spec.tls.key` | **allowed: the output starts with the PEM header of an RSA private key** |

Checks for indirect leaks, as the read-only user: no container of the
namespace has a literal password in its environment (all come from
Secrets); the ConfigMaps contain scripts that read passwords from files
at run time, no literal value; the OpenStackControlPlane spec (once
readable, next entry) has 13 `customServiceConfig` blocks, no password
assignment, only Secret names.

**Why / how it works**: `view` and `cluster-reader` deliberately exclude
Secrets and every sub-resource that gives a shell (`pods/exec`,
`pods/attach`, `nodes/proxy`). Because the OpenStack operators put all
credentials and all rendered configuration files (`nova.conf` with
database URLs, and so on) in Secrets, a read-only user sees service
health and logs but neither passwords nor effective configuration.
Kolla-Ansible equivalent: none; a Unix account that can read
`/etc/kolla` reads every password.

**Pitfalls**:

- **The private keys of the public endpoints are readable**: an
  OpenShift Route stores its certificate and key in its spec, and
  `view` includes Routes. A read-only user can copy the TLS key of
  every public OpenStack API (6 routes). If that matters, do not grant
  `view` on `openstack`; build a narrower Role without `routes`.
- Logs are readable, and OpenStack logs at debug level can contain
  tokens or request bodies. Read-only is not "no sensitive data".
- A read-only user cannot run any `openstack` command through the
  `openstackclient` pod (no exec). Give them a Keystone account with the
  `reader` role and a `clouds.yaml` on their own machine instead.
- Without the role of the next entry, the user cannot even list the
  OpenStackControlPlane, which makes the account of little use for
  diagnosis.

**See also**: [OpenStack identity](openstack-identity-and-tenants.md),
[Configuration, secrets and data](../concepts/04-configuration-secrets-and-data.md)

### How do I let read-only users see the OpenStack custom resources?

**Context**: a `cluster-reader` user gets `Forbidden` on
`oc get openstackcontrolplane`.

**How**:

**[CHANGE]** — creates one ClusterRole aggregated into `view` and
`cluster-reader`; no effect on workloads.

```bash
GROUPS_JSON=$(oc api-resources --no-headers -o name | grep -E '\.openstack\.org$' \
  | sed -E 's/^[^.]+\.//' | sort -u | python3 -c 'import sys,json; print(json.dumps([l.strip() for l in sys.stdin]))')
cat <<EOF | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openstack-cr-view
  labels:
    rbac.authorization.k8s.io/aggregate-to-view: "true"
    rbac.authorization.k8s.io/aggregate-to-cluster-reader: "true"
rules:
- apiGroups: ${GROUPS_JSON}
  resources: ["*"]
  verbs: ["get", "list", "watch"]
EOF
oc --kubeconfig=$V get openstackcontrolplane,keystoneapi,galera,openstackdataplanenodeset -n openstack
oc --kubeconfig=$V auth can-i patch openstackcontrolplanes.core.openstack.org -n openstack
```

**Observed on the lab** (2026-11-12):

```text
clusterrole.rbac.authorization.k8s.io/openstack-cr-view created
NAME        STATUS   MESSAGE
openstack   True     Setup complete
keystoneapi.keystone.openstack.org/keystone   True   Setup complete
galera.mariadb.openstack.org/openstack        True   Setup complete
openstackdataplanenodeset.dataplane.openstack.org/openstack-edpm   True   NodeSet Ready
no
```

31 API groups end in `.openstack.org` on this installation (104
resource types). A first attempt with `apiGroups: ["*.openstack.org"]`
was accepted by the API and granted nothing: RBAC has no partial
wildcard, only the exact name or `*` alone. The role was deleted after
the test.

**Why / how it works**: `view`, `edit`, `admin` and `cluster-reader` are
aggregated ClusterRoles: the controller manager merges into them the
rules of every ClusterRole carrying the matching `aggregate-to-*` label.
OLM creates such roles only for the one CRD owned by the installed
bundle (`openstacks.operator.openstack.org-v1beta1-view`, `-edit`,
`-admin`); the CRDs that the initialisation resource installs afterwards
(control plane, services, data plane) get none. So by default only
cluster administrators and the operators themselves can read them.
Kolla-Ansible equivalent: none.

**Pitfalls**:

- The group list is frozen at creation: after an operator update that
  adds an API group, regenerate the role.
- Custom resources can embed sensitive text: anything written in a
  `customServiceConfig` is visible to these readers. Passwords belong in
  a Secret referenced by `customConfigSecrets`-type fields, never
  inline.
- Do not add `aggregate-to-edit` without thought: `edit` on
  OpenStackControlPlane is full control of the cloud.

**See also**:
[Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md),
[OLM and operators](okd-olm-and-operators.md)

### How do I remove a user or the identity provider cleanly?

**Context**: a colleague leaves, or the throwaway accounts of a test
must disappear.

**How**:

**[CHANGE]**

```bash
# one user
oc adm policy remove-cluster-role-from-user cluster-admin ops-admin      # 1. bindings first
oc get clusterrolebinding,rolebinding -A -o wide | grep ops-admin        #    nothing must remain
oc get oauthaccesstokens -o json | python3 -c '
import json, sys
for t in json.load(sys.stdin)["items"]:
    if t["userName"] == "ops-admin": print(t["metadata"]["name"])' | xargs -r oc delete oauthaccesstokens   # 2. tokens
oc delete user ops-admin; oc delete identity local:ops-admin              # 3. objects
#    4. remove the line from the htpasswd file and update the Secret

# the whole provider
oc patch oauth cluster --type json -p '[{"op":"remove","path":"/spec/identityProviders"}]'
oc delete secret -n openshift-config local-htpasswd
oc get users,identities; oc get oauth cluster -o jsonpath='{.spec}{"\n"}'; oc get co authentication
```

**Observed on the lab** (2026-11-12): the administrator token was tested
with `oc get nodes` after each step.

```text
identity provider removed from OAuth     -> token still works
User and Identity deleted                -> token still works
OAuthAccessTokens deleted                -> token still works (tested within one second)
bindings removed, Secret deleted
leftovers: 0 bindings, no User, no Identity, oauth spec {}
authentication  Available=True  Progressing=True -> False   (OAuth pod rolled again, about one minute later)
```

**Why / how it works**: RBAC bindings name a user by a plain string and
tokens are independent objects: deleting the `User` does not delete
either. A valid token of a deleted user keeps the permissions of every
binding that still carries the name, and a new user created later with
the same name inherits those bindings. The API server also caches token
validations for a short time, which is why the token still answered
immediately after its deletion (the kubeconfig was then destroyed; the
exact delay was not measured). Kolla-Ansible equivalent: `userdel` and
removal of the SSH key.

**Pitfalls**:

- Order matters: bindings, then tokens, then User and Identity. Deleting
  only the User (the intuitive action) revokes nothing for up to 24
  hours.
- Removing a user from the htpasswd file only prevents new logins.
- A `User` deleted without its `Identity` blocks a later login of the
  same name (`mappingMethod: claim`; documented behaviour, not
  reproduced here): delete both objects.
- After removing the provider, check that nobody depended on it and
  that the certificate kubeconfig still works before closing the
  session.

**See also**:
[Safe change checklist](../operations/09-safe-change-checklist.md)

### Which permissions do the OpenStack operators hold, and who can edit the OpenStackControlPlane?

**Context**: security review, or "could this operator have deleted
that?".

**How**:

**[READ-ONLY]**

```bash
oc adm policy who-can patch openstackcontrolplanes.core.openstack.org -n openstack
oc get clusterrolebinding -o wide | grep openstack-operators | awk '{print $1, $2}'
oc get clusterrole openstack-operator-manager-role -o json | python3 -c '
import json, sys
r = json.load(sys.stdin)["rules"]; print("rules:", len(r))
for x in r:
    if "" in x.get("apiGroups", []): print(" core:", x["resources"], x["verbs"])'
oc get rolebinding -n openstack; oc get sa -n openstack
oc get role -n openstack nova-nova-role -o jsonpath='{.rules}{"\n"}'
```

**Observed on the lab** (2026-11-12):

```text
Users:  system:admin
        system:serviceaccount:openstack-operators:openstack-operator-controller-manager
        system:serviceaccount:openshift-operator-lifecycle-manager:olm-operator-serviceaccount
        ... 27 other platform service accounts that are cluster-admin
Groups: system:cluster-admins  system:masters
barbican-operator-manager-rolebinding   ClusterRole/barbican-operator-manager-role
...                                     # one manager role + one metrics role per service operator
openstack-operator-manager-role rules: 76
 core: ['configmaps', 'services'] ['*']
 core: ['namespaces'] ['*']
 core: ['pods', 'secrets'] ['create', 'delete', 'get', 'list', 'patch', 'update', 'watch']
 core: ['serviceaccounts'] ['*']
keystone-keystone-rolebinding   Role/keystone-keystone-role        # one Role + ServiceAccount per service
nova-nova-rolebinding           Role/nova-nova-role
[{"apiGroups":["security.openshift.io"],"resourceNames":["anyuid"],"resources":["securitycontextconstraints"],"verbs":["use"]}]
```

Three layers:

| Layer | Identity | Rights |
|---|---|---|
| Operators | one ServiceAccount per operator in `openstack-operators`, bound **cluster-wide** to `<service>-operator-manager-role` | read and write Secrets, ConfigMaps, Services, workloads and their own CRs in **every** namespace |
| Service pods | one ServiceAccount per service in `openstack` (`nova-nova`, `keystone-keystone`, ...) | only "use the `anyuid` SCC" (Galera also manages pods and Services of its namespace, for its own cluster state) |
| Humans | whoever is cluster-admin | everything; nobody else can read or edit the OpenStack CRs |

About 79 ClusterRoles belong to the OpenStack operators (378 in the
cluster).

**Why / how it works**: the operator bundle declares the permissions its
controllers need and OLM (or the initialisation resource of the
openstack-operator, for the service operators) creates the roles and
bindings. They are ClusterRoleBindings because an operator may manage
control planes in any namespace. The pods of the control plane
themselves hold almost no API permission: a compromised Keystone
container cannot read the Secrets of Nova through the Kubernetes API.
Kolla-Ansible equivalent: the deployment user with sudo on every host —
comparable to the operators' ServiceAccounts.

**Pitfalls**:

- Any operator ServiceAccount can read every Secret of the cluster,
  including those of other namespaces. The operators' namespace must be
  protected like the control plane itself (who can `exec` into, or
  create pods in, `openstack-operators`?).
- There is no built-in "OpenStack operator" role for humans between
  read-only and cluster-admin. Delegating day-to-day operations needs a
  custom Role on `openstack` (CRs, pods, `pods/exec`, Secrets), which is
  in practice full control of the cloud.
- `who-can` lists the garbage collector and OLM among the editors: they
  are expected, and they do not edit specs.

**See also**: [OLM and operators](okd-olm-and-operators.md),
[From Kolla to operators](../concepts/01-from-kolla-to-operators.md)

### Under which security context do the OpenStack pods run?

**Context**: a pod refused with "unable to validate against any security
context constraint", or a file permission problem on a volume.

**How**:

**[READ-ONLY]**

```bash
oc get pods -n openstack -o json | python3 -c '
import json, sys
for p in json.load(sys.stdin)["items"]:
    if p["status"]["phase"] != "Running": continue
    sc = p["spec"].get("securityContext", {})
    uid = {str((c.get("securityContext") or {}).get("runAsUser", sc.get("runAsUser", "-"))) for c in p["spec"]["containers"]}
    print("%-28s scc=%-13s sa=%-30s uid=%-10s fsGroup=%s" % (p["metadata"]["name"][:28],
          p["metadata"]["annotations"].get("openshift.io/scc"), p["spec"]["serviceAccountName"], ",".join(uid), sc.get("fsGroup", "-")))'
oc get ns openstack -o jsonpath='{.metadata.labels}{"\n"}'
oc get scc
oc adm policy who-can use scc anyuid -n openstack | grep serviceaccount:openstack:
```

**Observed on the lab** (2026-11-12):

```text
dnsmasq-dns-<hash>        scc=restricted-v2 sa=dnsmasq-dns          uid=1000770000 fsGroup=1000770000
glance-default-single-0   scc=privileged    sa=glance-glance        uid=42415      fsGroup=42415
keystone-<hash>           scc=anyuid        sa=keystone-keystone    uid=42425      fsGroup=-
neutron-<hash>            scc=anyuid        sa=neutron-neutron      uid=42435      fsGroup=42435
nova-api-0                scc=anyuid        sa=nova-nova            uid=42436      fsGroup=-
openstack-galera-0        scc=anyuid        sa=galera-openstack     uid=-          fsGroup=-
ovsdbserver-nb-0          scc=restricted-v2 sa=ovncluster-ovndbcluster-nb  uid=1000770000 fsGroup=1000770000
rabbitmq-server-0         scc=anyuid        sa=rabbitmq-server      uid=999        fsGroup=0
...
{"kubernetes.io/metadata.name":"openstack","pod-security.kubernetes.io/enforce":"privileged","security.openshift.io/scc.podSecurityLabelSync":"false"}
```

Of 20 running pods: 15 `anyuid`, 4 `restricted-v2` (the OVN databases,
northd, dnsmasq), 1 `privileged` (Glance). None runs a privileged
container, none uses the host network.

**Why / how it works**: a SecurityContextConstraint (SCC) is the
OpenShift admission rule that decides which user ID, capabilities and
host accesses a pod may ask for. `restricted-v2`, the default, forces a
random UID from the namespace's range (1000770000 here). The OpenStack
images are the Kolla-style ones with fixed UIDs (42436 = nova, 42425 =
keystone...), so each service's ServiceAccount is allowed to use
`anyuid`. The namespace is labelled `enforce: privileged` at
installation so that Pod Security admission does not reject these pods.
Kolla-Ansible equivalent: the same UIDs inside the containers, with
Docker running everything as root-capable.

**Pitfalls**:

- The SCC shown is the one admission selected, not necessarily the
  least permissive that would work: Glance gets `privileged` because its
  ServiceAccount is allowed it and its pod spec matches, while no
  container is actually privileged.
- A pod you create yourself in `openstack` with the `default`
  ServiceAccount gets `restricted-v2` and a random UID: it cannot read
  files owned by 42436 on a volume. Use the service's ServiceAccount
  for debug pods, or `oc debug` on the existing workload.
- The fixed UIDs are those of the files on the local PVs: a volume
  written by Galera (UID 42434 inside the image) must not be reused for
  another service without cleaning.
- Removing the namespace labels makes the next pod recreation fail, not
  the running pods: the damage appears at the next restart.

**See also**:
[Pod pending or CrashLoop](../troubleshooting/pod-pending-or-crashloop.md),
[Storage](okd-storage.md)

### Who changed the OpenStackControlPlane (or logged in)? Querying the audit log

**Context**: a configuration changed and nobody remembers doing it.

**How**:

**[READ-ONLY]**

```bash
oc get apiserver cluster -o jsonpath='{.spec.audit}{"\n"}'
oc adm node-logs okd-0 --path=kube-apiserver/              # audit.log + rotated files
# human changes to the control plane resource, over every retained file
for f in $(oc adm node-logs okd-0 --path=kube-apiserver/ | grep -E '^audit'); do
  oc adm node-logs okd-0 --path=kube-apiserver/$f \
  | grep '"resource":"openstackcontrolplanes"' | grep -v '"username":"system:serviceaccount' \
  | grep -E '"verb":"(patch|update|create|delete)"' | grep '"stage":"ResponseComplete"' \
  | python3 -c '
import json, sys
for l in sys.stdin:
    e = json.loads(l)
    print(e["requestReceivedTimestamp"][:19], e["verb"], e["user"]["username"], e["responseStatus"]["code"],
          e["sourceIPs"][0], e.get("userAgent", "").split(" ")[0], e["annotations"].get("authorization.k8s.io/reason", "")[:60])'
done | sort
# logins (password checks) are in the OAuth server audit log
oc adm node-logs okd-0 --path=oauth-server/audit.log | grep '"authentication.openshift.io/username"' | python3 -c '
import json, sys
for l in sys.stdin:
    e = json.loads(l); a = e["annotations"]
    print(e["requestReceivedTimestamp"][:19], a.get("authentication.openshift.io/username"), a.get("authentication.openshift.io/decision"), e["sourceIPs"][0])'
```

**Observed on the lab** (2026-11-12):

```text
{"profile":"Default"}
audit-2026-11-12T03-21-13.628.log ... audit.log                # 10 files, about 10 hours
2026-11-12T07:05:36 patch system:admin 200 192.168.130.5 oc/4.22.0
2026-11-12T07:38:31 patch system:admin 200 192.168.130.5 oc/4.22.0
2026-11-12T07:40:26 patch system:admin 200 192.168.130.5 oc/4.22.0
2026-11-12T11:37:26 patch system:admin 200 192.168.130.5 oc/4.22.0
2026-11-12T12:14:56 patch <named admin> 200 192.168.130.5 oc/4.22.0 RBAC: allowed by ClusterRoleBinding "cluster-admin-0" of Clu...
2026-11-12T12:14:21 <named admin> allow 10.128.0.2           # OAuth server log
```

The morning's changes all read `system:admin` from the bastion address:
with a shared certificate the audit log says when and from where, not
who. The test annotation made with the named account is attributed, with
the binding that allowed it.

**Why / how it works**: every API request produces JSON lines in
`/var/log/kube-apiserver/audit.log` on the node (the OpenShift and
OAuth API servers have their own directories). The `Default` profile
records metadata only — who, verb, resource, response code — not the
content of the change. `oc adm node-logs` reads the files through the
kubelet. Kolla-Ansible equivalent: shell history and `git log` of the
configuration repository; nothing at API level.

**Pitfalls**:

- Retention is by size: 10 files of 200 MB, about **10 hours** on this
  idle lab (see the node entry on log retention). A change older than
  that is gone; the next best sources are
  `metadata.managedFields` of the object (manager name and time of the
  last write per field) and the `ControllerRevision`/ReplicaSet
  history.
- The log shows that a patch happened, not what it changed. To record
  request bodies, set `spec.audit.profile: WriteRequestBodies` on
  `apiserver/cluster` — it rolls the API server and multiplies the
  volume, so retention in hours shrinks; not done on the lab.
- Filter on `"stage":"ResponseComplete"`, otherwise each request appears
  twice or more.
- Changes made by operators appear under their ServiceAccount and are
  far more numerous (status updates); exclude
  `system:serviceaccount` first, then look at them if no human matches.
- The OAuth server log shows 10.128.0.2 (the node's port on the pod
  network) as the source of every login: the router hides the real
  client address. Logins cannot be traced to a workstation from here.
- Changes inside OpenStack (who deleted an instance) are not here: they
  are in the OpenStack API logs, by request ID.

**See also**:
[How long are host logs kept](okd-node-and-host.md#how-long-are-host-logs-kept-journal-container-logs-audit),
[Logs](../operations/02-logs.md)

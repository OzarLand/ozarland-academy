# OpenStack service administration through operators

> Status: every command was run on the lab (OKD 4.22, operators 18-stable,
> OpenStack 2023.1 Antelope, one KVM compute node) on 2026-11-12

Every control-plane service is described by the `OpenStackControlPlane`
resource `openstack` (short name `oscp`) in the namespace `openstack`.
You change the resource; the operators render configuration into Secrets
and roll the pods. Commands run on the bastion with `oc project openstack`
done. `os` is the admin client:

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
```

## Entries

### Where is the configuration of a service and what did the operator put in it?

**Context**: with Kolla-Ansible you read `/etc/kolla/<service>/`. Here the
file lives in a Secret and is mounted in the pod.

**How**:

**[READ-ONLY]**

```bash
oc get pods -o custom-columns=POD:.metadata.name,SERVICE:.metadata.labels.service,CONTAINERS:.spec.containers[*].name
oc get secrets | grep config-data
oc get secret nova-api-config-data -o json | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)["data"].keys()))'
oc exec nova-api-0 -c nova-api-api -- ls /etc/nova /etc/nova/nova.conf.d
oc exec nova-api-0 -c nova-api-api -- grep -E '^(debug|enforce_|policy_file|log_file)' /etc/nova/nova.conf.d/01-nova.conf
oc explain openstackcontrolplane.spec.placement.template | grep -E 'customServiceConfig|defaultConfigOverwrite'
```

**Observed on the lab** (2026-11-12):

```text
nova-api-0     nova-api    nova-api-log,nova-api-api
['01-nova.conf', 'httpd.conf', 'my.cnf', 'nova-api-config.json', 'nova-blank.conf', 'ssl.conf']
debug=true
enforce_new_defaults=true
enforce_scope=true
log_file = /var/log/nova/nova-api.log
policy_file=/etc/nova/policy.yaml
```

Layout per service: Keystone `/etc/keystone/keystone.conf` plus
`keystone.conf.d/custom.conf`; Glance `/etc/glance/glance.conf.d/00..03-config.conf`;
Placement `placement.conf` plus `placement.conf.d/custom.conf`; Neutron
`neutron.conf.d/01-neutron.conf` and `02-neutron-custom.conf`; Nova
`nova.conf.d/01-nova.conf`. Defaults worth knowing: secure RBAC is on
everywhere (`enforce_new_defaults`, `enforce_scope`), Nova and Placement
run with `debug = true`, Keystone does not; notifications use the `noop`
driver in Glance, Neutron and Nova and `messagingv2` in Keystone.

**Why / how it works**: each service operator renders templates into a
Secret `<service>-config-data` owned by its custom resource; the pod
mounts it and the Kolla entry point copies the files into `/etc`. What
you write in `customServiceConfig` lands in the last file of the
`.conf.d` directory, so it wins. Kolla-Ansible equivalent:
`/etc/kolla/config/<service>.conf` merged by `kolla-ansible reconfigure`.

**Pitfalls**:

- Container names are not the pod name: `nova-api-0` has `nova-api-log`
  and `nova-api-api`, Glance `glance-log` and `glance-httpd`, Neutron
  `neutron-api` and `neutron-httpd`. `oc exec` without `-c` picks the
  first one, often the log sidecar.
- The configuration files contain database and RabbitMQ passwords
  (`transport_url`, `connection`). Use `grep` with a precise pattern, never
  `cat`.
- Editing the Secret or the file in the pod is reverted at the next
  reconciliation.
- Not every service has the same knobs: Keystone, Placement, Neutron and
  Nova have `defaultConfigOverwrite`; Glance has
  `customServiceConfigSecrets` instead.

**See also**: [Configuration, secrets and data](../concepts/04-configuration-secrets-and-data.md),
[Change service configuration](../operations/04-change-service-configuration.md),
[Manual changes reverted](../troubleshooting/manual-changes-reverted.md)

### How do I override one policy rule of a service?

**Context**: a team needs one extra right (here: project members may list
resource providers). With Kolla-Ansible you drop a `policy.yaml` in
`/etc/kolla/config/placement/`.

**How**:

**[CHANGE]** Rolls the Placement pods.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"placement":{"template":{"defaultConfigOverwrite":{"policy.yaml":"\"placement:resource_providers:list\": \"role:member\"\n"}}}}}'
oc rollout status deployment/placement --timeout=300s
oc wait oscp openstack --for=condition=Ready --timeout=300s
```

**[READ-ONLY]**

```bash
pp=$(oc get pod -l service=placement -o name | sed -n 1p)
oc exec $pp -c placement-api -- cat /etc/placement/policy.yaml
oc get secret placement-config-data -o json | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)["data"].keys()))'
```

**[CHANGE]** Revert.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"placement":{"template":{"defaultConfigOverwrite":null}}}}'
```

**Observed on the lab** (2026-11-12): before the change the member got
`Policy does not allow placement:resource_providers:list to be performed.
(HTTP 403)`. The patch was applied at 07:05:36 and the control plane was
Ready again at 07:06:00 (24 s). The file appeared in the pod, the Secret
gained a `policy.yaml` key, the member could list providers and still got
403 on inventories. The revert took 23 s; the file was gone and the 403
was back.

**Why / how it works**: `defaultConfigOverwrite` is a map of file name to
content; the operator adds each entry to the configuration Secret, the
changed hash triggers a rolling update, and `policy_file` already points
to `/etc/<service>/policy.yaml`. Kolla-Ansible equivalent:
`/etc/kolla/config/<service>/policy.yaml` and `kolla-ansible reconfigure`.

**Pitfalls**:

- Only `policy.yaml` was tested. Which other file names each operator
  accepts in this map was not checked.
- JSON in a shell: the rule needs escaped quotes and a trailing `\n`. Nothing
  validates the content before the rollout: test with a member token
  right after it.
- Right after the patch two pods exist for a few seconds (old one
  terminating): `oc get pod -l service=placement -o name` returns two
  names. Wait for the rollout before you look inside.
- With `enforce_new_defaults = true`, rules use the roles `reader`,
  `member`, `admin`; old rules based on `is_admin` or `owner` do not match
  what the service evaluates.

**See also**: [Change service configuration](../operations/04-change-service-configuration.md),
[Safe change checklist](../operations/09-safe-change-checklist.md),
[identity and tenants](openstack-identity-and-tenants.md)

### How do I turn on debug logging for one service and turn it off again?

**Context**: you need detail from Keystone for a few minutes.

**How**:

**[CHANGE]** Rolls the Keystone pod; tokens stay valid.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"keystone":{"template":{"customServiceConfig":"[DEFAULT]\ndebug = true\n"}}}}'
oc rollout status deployment/keystone --timeout=300s
oc wait oscp openstack --for=condition=Ready --timeout=300s
```

**[READ-ONLY]**

```bash
kp=$(oc get pod -l service=keystone -o name | sed -n 1p)
oc exec $kp -c keystone-api -- cat /etc/keystone/keystone.conf.d/custom.conf
oc logs $kp -c keystone-api --since=6m | grep -c DEBUG
oc get oscp openstack -o jsonpath='keystone=[{.spec.keystone.template.customServiceConfig}]{"\n"}'
```

**[CHANGE]** Revert.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"keystone":{"template":{"customServiceConfig":null}}}}'
```

**Observed on the lab** (2026-11-12): rollout 35 s each way (07:06:30 to
07:07:05, then 07:07:42 to 07:08:17). `custom.conf` contained the two
lines; the pod wrote 1621 DEBUG lines in six minutes of light use, none
before. A member token could be issued during and after both rollouts.
Keystone log lines carry the Apache prefix:

```text
[Thu Nov 12 07:07:03.395433 2026] [wsgi:error] [pid 19:tid 47] 2026-11-12 07:07:03.395 19 DEBUG mod_wsgi [-] Configuration options gathered from: ...
```

**Why / how it works**: `customServiceConfig` is written to
`custom.conf` in the service's `.conf.d` directory and the Deployment is
rolled because the configuration hash changes. Kolla-Ansible equivalent:
`openstack_logging_debug: "True"` (all services) or a per-service
override, then `kolla-ansible reconfigure -t keystone`.

**Pitfalls**:

- With one replica, a rollout is a short API interruption for clients
  that do not retry. The lab runs one Keystone pod.
- Debug output starts with a dump of **all** options at start-up and is
  much more verbose about requests: do not paste debug logs unfiltered.
- `customServiceConfig` replaces the whole snippet: patching it with
  `null` also removes anything that was there before. Check the current
  value first.
- Under `set -o pipefail`, `oc logs ... | head` aborts a script before
  the revert step. Use `sed -n '1,5p'`.

**See also**: [Logs](../operations/02-logs.md),
[Change service configuration](../operations/04-change-service-configuration.md),
[Restart a service](../operations/03-restart-a-service.md)

### Who rotates the Keystone Fernet keys?

**Context**: with Kolla-Ansible a cron job in the `keystone_fernet`
container rotates keys and pushes them to the other controllers. Here
there is no such container.

**How**:

**[READ-ONLY]** Key names and metadata only; never print the values.

```bash
oc get secret keystone -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sorted(d["data"].keys())); print(d["metadata"]["annotations"].get("keystone.openstack.org/rotatedat"))'
oc get keystoneapi keystone -o jsonpath='rot={.spec.fernetRotationDays} max={.spec.fernetMaxActiveKeys}{"\n"}'
kp=$(oc get pod -l service=keystone -o name | sed -n 1p)
oc exec $kp -c keystone-api -- ls /etc/keystone/fernet-keys/ /etc/keystone/credential-keys/
oc get cronjob keystone-cron -o jsonpath='{.spec.schedule} {.spec.jobTemplate.spec.template.spec.containers[0].command}{"\n"}'
```

**Observed on the lab** (2026-11-12):

```text
['CredentialKeys0', 'CredentialKeys1', 'FernetKeys0', 'FernetKeys1', 'FernetKeys2', 'FernetKeys3', 'FernetKeys4']
2026-11-11T20:25:26Z
rot=1 max=5
1 * * * * ["keystone-manage","trust_flush"]
```

The pod sees the keys as files `0` to `4` under
`/etc/keystone/fernet-keys/` (projected Secret, symbolic links to
`..data`).

**Why / how it works**: the keystone operator owns the Secret `keystone`.
It rotates the keys itself when the annotation `rotatedat` is older than
`fernetRotationDays`, and the kubelet refreshes the mounted files without
a pod restart. The only CronJob, `keystone-cron`, flushes expired trusts
every hour. Kolla-Ansible equivalent: `keystone_fernet` container with
cron and rsync, period from `fernet_token_expiry`.

**Pitfalls**:

- The Secret holds the keys of every token of the cloud. It is part of
  what the control-plane export saves: keep that backup directory private.
- Losing this Secret means losing every issued token and every stored
  credential encrypted with the credential keys. Never delete it to
  "force a rotation".
- The rotation comes with the first reconciliation after the period,
  not exactly 24 hours after the previous one; the next entry shows one.
- The resource offers no field to trigger a rotation by hand: the only
  settings are `fernetRotationDays` and `fernetMaxActiveKeys`. Editing
  the annotation or the Secret to provoke one is not a documented
  interface and was not tried.

**See also**: [Passwords and secrets](../operations/07-passwords-and-secrets.md),
[Backup and restore](../lifecycle/05-backup-and-restore.md)

### How do I watch a Fernet rotation and check that issued tokens survive it?

**Context**: you want proof that the automatic rotation happens, that
the pod picks up the new keys without restart, and that tokens issued
before the rotation stay valid, without ever printing a key.

**How**:

**[READ-ONLY]** One sample: when the Secret was last rotated, a short
fingerprint of each key in the Secret and of each key file in the pod,
and the pod's restart count. Six hexadecimal characters of a SHA-256
identify a key without revealing it.

```bash
oc get secret keystone -o jsonpath='{.metadata.annotations.keystone\.openstack\.org/rotatedat} rv={.metadata.resourceVersion}{"\n"}'
oc get secret keystone -o json | python3 -c '
import json, sys, base64, hashlib
d = json.load(sys.stdin)["data"]
print(" ".join(f"{k}={hashlib.sha256(base64.b64decode(v)).hexdigest()[:6]}" for k, v in sorted(d.items())))'
kp=$(oc get pod -l service=keystone -o name | sed -n 1p)
oc exec $kp -c keystone-api -- sh -c 'cd /etc/keystone/fernet-keys && for f in *; do printf "%s=%s " "$f" "$(sha256sum "$f" | cut -c1-6)"; done; echo'
oc get $kp -o jsonpath='{.metadata.name} restarts={.status.containerStatuses[0].restartCount}{"\n"}'
```

**[READ-ONLY]** Token survival: keep one token in a file readable by
you only, and ask Keystone to validate it at each sample (`200` means
valid). The token is a credential: mode 600, never in a log, removed at
the end.

```bash
( umask 077; os token issue -f value -c id > .work/fernet-tok-a )
url=$(os endpoint list --service identity --interface public -f value -c URL)
curl -sk -o /dev/null -w '%{http_code}\n' -H "X-Auth-Token: $(cat .work/fernet-tok-a)" -H "X-Subject-Token: $(cat .work/fernet-tok-a)" "$url/v3/auth/tokens"
rm -f .work/fernet-tok-a
```

On the lab these samples are taken every two minutes by a small script
started with `nohup` on the bastion; it stops by itself.

**Observed on the lab** (2026-11-12): the Secret had last been rotated
on 2026-11-11 at 20:25:26 UTC. With `fernetRotationDays: 1` it was not
rotated at 20:25 the next day but at 21:01:00 UTC, 24 h 35 min after the
previous rotation: the operator rotates during the first reconciliation
of the `KeystoneAPI` that comes after the period, and the one that did
it started at the same second as the hourly `keystone-cron` Job
(minute 1 of each hour).

```text
before  (20:48)  rotatedat 2026-11-11T20:25:26Z
  FernetKeys0=<A> FernetKeys1=<B> FernetKeys2=<C> FernetKeys3=<D> FernetKeys4=<E>
after   (21:02)  rotatedat 2026-11-12T21:01:00Z, new resourceVersion
  FernetKeys0=<new> FernetKeys1=<C> FernetKeys2=<D> FernetKeys3=<E> FernetKeys4=<A>
  CredentialKeys0, CredentialKeys1: unchanged
files in the pod: 0=<new> 1=<C> 2=<D> 3=<E> 4=<A>, "..data" link dated 21:01:09
keystone pod: same pod, restart count unchanged
```

- The staged key `0` (`<A>`) became the primary key under the highest
  index, a new staged key `0` was generated, the oldest secondary key
  (`<B>`) was dropped and the others moved down by one.
- The files mounted in the pod were replaced 9 s after the Secret, with
  no restart of Keystone.
- The previous primary key (`<E>`) is still present as a secondary key:
  tokens issued before the rotation remain decryptable. The watcher
  described above had stopped at 20:50 UTC, 11 minutes before the
  rotation, so the `validate=HTTP 200` across the rotation was not
  recorded: start such a watcher with a margin of more than one hour
  after the theoretical time.
- Two node reboots during the day restarted the Keystone pod; the keys
  did not change and tokens issued before the reboots stayed valid.

**Why / how it works**: a Fernet token is encrypted with the primary
key and can be decrypted by any key still in the repository. A rotation
promotes the staged key to primary and keeps the previous primaries as
secondary keys, so a token stays valid as long as the key that
encrypted it has not been pushed out: with 5 keys and one rotation a
day, about three days, far longer than the token lifetime. Kolla-Ansible
equivalent: `keystone-manage fernet_rotate` from cron in the
`keystone_fernet` container, then rsync to the other controllers.

**Pitfalls**:

- Do not write a watcher that prints the Secret or a token: a
  fingerprint and an HTTP status are enough.
- The same Secret holds the credential keys; they are not rotated by
  this mechanism (their fingerprints are in the log to confirm it).
- The rotation does not happen at a fixed time of day: it waits for a
  reconciliation after the period has elapsed, here 36 minutes late.

**See also**: [Passwords and secrets](../operations/07-passwords-and-secrets.md),
[open questions](open-questions.md)

### Who creates the catalog endpoints and what happens if one is deleted?

**Context**: with Kolla-Ansible the `service-ks-register` role creates
endpoints at deploy time. Somebody deleted one by mistake.

**How**:

**[READ-ONLY]**

```bash
os endpoint list -f value -c "Service Name" -c "Service Type" -c Interface -c URL | sort
oc get keystoneservice,keystoneendpoint
oc get keystoneendpoint placement -o jsonpath='{.spec.endpoints}{"\n"}'
```

**[DESTRUCTIVE]** The mistake, reproduced on Placement's public endpoint.

```bash
os endpoint delete "$(os endpoint list --service placement --interface public -f value -c ID)"
```

**[CHANGE]** Force a reconciliation of the owning resource.

```bash
oc annotate keystoneendpoint placement kb1/poke="$(date +%s)" --overwrite
oc logs -n openstack-operators deploy/keystone-operator-controller-manager --since=5m | grep -i endpoint | tail -2
```

**Observed on the lab** (2026-11-12): ten endpoints, public and internal
for five services:

```text
keystone identity internal https://keystone-internal.openstack.svc:5000
keystone identity public https://keystone-public-openstack.apps.okd.lab.example.com
nova compute internal https://nova-internal.openstack.svc:8774/v2.1
nova compute public https://nova-public-openstack.apps.okd.lab.example.com/v2.1
```

After the deletion the endpoint was **not** recreated during 2 min 20 s
and the resource kept showing `True / Setup complete`. Within 12 s of
the annotation the endpoint was back. The keystone operator log of the
previous twelve hours shows `Reconciled Endpoints successfully` only at
installation time and at the annotation: no periodic pass in between.

**Why / how it works**: each service operator creates a `KeystoneService`
and a `KeystoneEndpoint` resource; the keystone operator turns them into
catalog entries and stores the IDs in the status. It reacts to changes of
the Kubernetes object, not of the Keystone database, so drift on the
OpenStack side is only repaired at the next reconciliation. Any metadata
change triggers one. Kolla-Ansible equivalent:
`kolla-ansible deploy -t keystone` (or the service tag) re-registers
endpoints.

**Pitfalls**:

- There is no `KeystoneEndpoint` for Keystone itself: its own endpoints
  come from the bootstrap job. Do not delete those.
- `Setup complete` on the resource does not prove the catalog is intact.
  Compare with `openstack endpoint list`.
- There are no `admin` interface endpoints, only `public` and `internal`.
- Looking up a service by name with the CLI writes a
  `ServiceNotFound` traceback in the Keystone log before the client
  retries by ID. It is noise, not an incident.

**See also**: [Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md),
[Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md),
[Manual changes reverted](../troubleshooting/manual-changes-reverted.md)

### How do I inspect RabbitMQ: users, queues, connections, alarms?

**Context**: RPC timeouts, "is the broker healthy, who is connected,
which queues pile up?"

**How**:

**[READ-ONLY]** Same commands on `rabbitmq-cell1-server-0` for the cell
broker.

```bash
r() { oc exec rabbitmq-server-0 -c rabbitmq -- "$@"; }
r rabbitmqctl cluster_status
r rabbitmqctl list_vhosts
r rabbitmqctl list_users
r rabbitmqctl list_permissions -p /
r rabbitmqctl list_queues -q name messages consumers type
r rabbitmqctl list_connections -q user ssl ssl_protocol
r rabbitmqctl list_exchanges -q name type
r rabbitmqctl list_bindings -q source_name destination_name routing_key
r rabbitmq-diagnostics -q check_running
r rabbitmq-diagnostics -q check_local_alarms
r rabbitmq-diagnostics -q memory_breakdown --unit MB
r rabbitmq-diagnostics -q listeners
```

**Observed on the lab** (2026-11-12): RabbitMQ 4.2.9 on Erlang 26, one
node per broker, no alarm.

```text
default_user_rabbitmq   [administrator]
notifications.info              135  0  quorum
barbican_notifications.info     135  0  quorum
scheduler.nova-scheduler-0      0    1  quorum
q-plugin.neutron-<old-pod>      0    0  quorum
     15 default_user_rabbitmq  true  tlsv1.3
Interface: [::], port: 5671, protocol: amqp/ssl, purpose: AMQP 0-9-1 and AMQP 1.0 over TLS
Interface: [::], port: 15692, protocol: http/prometheus, purpose: Prometheus exporter API over HTTP
```

One vhost `/` and one administrator user shared by all services; 15
connections, all TLS 1.3; service queues are quorum queues, fan-out and
reply queues are classic. The cell broker holds the `compute.*` and
cell conductor queues.

**Why / how it works**: two brokers, `rabbitmq` (API level) and
`rabbitmq-cell1` (cell 1), each a StatefulSet managed through the
infrastructure operator. The services get the URL through their
configuration Secret (`transport_url` with `ssl=1`). Kolla-Ansible
equivalent: `docker exec rabbitmq rabbitmqctl ...`; one broker, user
`openstack`, TLS optional.

**Pitfalls**:

- `notifications.info` and `barbican_notifications.info` had 135 messages
  and **no consumer**: Keystone emits notifications (`messagingv2`) and
  nothing reads them, so these queues only grow.
- Each replaced Neutron pod leaves three queues named after the old pod
  with no consumer. They are quorum queues without expiry and no policy
  is defined (`rabbitmqctl list_policies` is empty), so they never go
  away: 15 such queues from five former pods after one day.
- Do not purge or delete queues to "clean up" without a decision: on
  quorum queues this is not reversible.
- A single user for every service means broker-side permissions do not
  separate services; the user's password is in the Secret
  `rabbitmq-default-user`. Do not print it.
- There is no `RabbitmqCluster` resource type on this version; do not
  follow guides that edit one.

**See also**: [Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md),
[Inspect service status](../operations/01-inspect-service-status.md)

### How do I look inside Galera: databases, sizes, connections, slow queries?

**Context**: capacity review or a slow API: is the database the cause?

**How**:

**[READ-ONLY]** The client in the pod authenticates by itself.

```bash
g() { oc exec openstack-galera-0 -c galera -- mysql -e "$1"; }
g "SELECT VERSION(); SHOW DATABASES;"
g "SELECT table_schema AS db, ROUND(SUM(data_length+index_length)/1024/1024,1) AS size_mb, COUNT(*) AS tables FROM information_schema.tables GROUP BY table_schema ORDER BY 2 DESC;"
g "SELECT user, db, COUNT(*) AS conns FROM information_schema.processlist GROUP BY user, db ORDER BY 3 DESC;"
g "SHOW GLOBAL STATUS WHERE Variable_name IN ('wsrep_cluster_size','wsrep_cluster_status','wsrep_local_state_comment','wsrep_ready','Threads_connected','Max_used_connections','Slow_queries');"
g "SHOW GLOBAL VARIABLES WHERE Variable_name IN ('slow_query_log','slow_query_log_file','long_query_time','max_connections','innodb_buffer_pool_size');"
g "SET SESSION long_query_time=0; SELECT SLEEP(0.2); SHOW SESSION STATUS LIKE 'Slow_queries';"
oc exec openstack-cell1-galera-0 -c galera -- mysql -e "SHOW DATABASES;"
oc get galera,mariadbdatabase,mariadbaccount
```

**Observed on the lab** (2026-11-12): MariaDB 10.5.29.

```text
db          size_mb  tables
neutron     11.1     189
nova_cell0  4.0      110
nova_api    1.7      32
keystone    1.6      49
glance      0.9      14
placement   0.6      13
wsrep_cluster_size 1, wsrep_cluster_status Primary, wsrep_local_state_comment Synced
Threads_connected 45, Max_used_connections 51, max_connections 4096
slow_query_log OFF, long_query_time 10, innodb_buffer_pool_size 134217728
```

Connections per service account: Neutron 14, Nova cell0 11, Nova API 9,
Glance 4, Placement 3, Keystone 3. The largest table is
`neutron.ml2_geneve_allocations` (65994 rows, 4 MB). `nova_cell1` lives in
the second instance `openstack-cell1`.

**Why / how it works**: two Galera instances managed by the mariadb
operator. Each service database is a `MariaDBDatabase`, each login a
`MariaDBAccount` whose user name is `<service>_<random suffix>`. Services
connect to the ClusterIP Service `openstack` (or `openstack-cell1`) on
3306. Kolla-Ansible equivalent: `docker exec mariadb mysql -u root -p`,
one cluster, users named after the service.

**Pitfalls**:

- You are `root` on the cloud's databases. Everything except `SELECT` and
  `SHOW` is outside read-only work; schema changes belong to the
  operators' db-sync jobs.
- The slow query log is **off** and the InnoDB buffer pool is the 128 MB
  default. Changing either means changing the Galera resource; it was
  not attempted here.
- The `SET SESSION` trial only affects your own session; it proves the
  counter works, not that the log file is written.
- Account names change when an account is recreated: never hard-code
  them in scripts.

**See also**: [Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md),
[Backup and restore](../lifecycle/05-backup-and-restore.md),
[Passwords and secrets](../operations/07-passwords-and-secrets.md)

### How do I take a database backup before a risky change?

**Context**: last step of the preparation of any exercise that touches
the control plane.

**How**:

**[READ-ONLY]**

```bash
oc get galerabackup
oc get cronjob | grep backup
ls ~/backups/
```

**[CHANGE]** One extra run of each backup CronJob.

```bash
for i in openstack openstack-cell1; do
  oc -n openstack create job --from=cronjob/backup-$i kb1-backup-$i
done
oc -n openstack wait job/kb1-backup-openstack job/kb1-backup-openstack-cell1 \
  --for=condition=complete --timeout=5m
```

**Observed on the lab** (2026-11-12):

```text
backup-openstack         @daily
backup-openstack-cell1   @daily
job.batch/kb1-backup-openstack         Complete   1/1   15s
job.batch/kb1-backup-openstack-cell1   Complete   1/1   15s
```

The dumps go to the volumes `mysql-backup-openstack` and
`mysql-backup-openstack-cell1` (10 Gi each). The bastion directory of the
previous night's control-plane export was still present.

**Why / how it works**: a `GaleraBackup` resource makes the mariadb
operator create a CronJob that writes logical dumps to its own volume. A
manual Job created from the CronJob template runs the same script
immediately. Kolla-Ansible equivalent:
`kolla-ansible mariadb_backup`.

**Pitfalls**:

- A Job that the CronJob controller did not create itself raises a
  Warning event `UnexpectedJob`. It is harmless.
- The backup volume is on the same disk as the database on the lab: it
  protects against a bad change, not against losing the node.
- A database dump alone is not a restore point: pair it with the export
  of the custom resources and Secrets.
- The restore was executed on both instances:
  [Backup and restore drills](backup-and-restore-drills.md).

**See also**: [Backup and restore](../lifecycle/05-backup-and-restore.md),
[Safe change checklist](../operations/09-safe-change-checklist.md)

### How do I check memcached?

**Context**: slow token validation or suspicion that the cache is full.

**How**:

**[READ-ONLY]**

```bash
oc get memcached
oc get svc memcached -o jsonpath='{.spec.ports[*].name} {.spec.ports[*].port}{"\n"}'
oc exec memcached-0 -c memcached -- bash -c 'exec 3<>/dev/tcp/127.0.0.1/11211; printf "stats\r\nquit\r\n" >&3; timeout 3 cat <&3 | grep -E "STAT (version|curr_connections|cmd_get|get_hits|get_misses|curr_items|limit_maxbytes|evictions) "'
oc exec memcached-0 -c memcached -- memcached-tool 127.0.0.1:11211 stats
kp=$(oc get pod -l service=keystone -o name | sed -n 1p)
oc exec $kp -c keystone-api -- grep -E '^(backend|memcache_servers|tls_enabled)' /etc/keystone/keystone.conf
```

**Observed on the lab** (2026-11-12):

```text
memcached-tls memcached 11212 11211
STAT version 1.6.9
STAT curr_connections 28
STAT cmd_get 57006
STAT get_hits 56638
STAT get_misses 368
STAT limit_maxbytes 10414456832
STAT curr_items 566
STAT evictions 0
backend = oslo_cache.memcache_pool
memcache_servers=memcached-0.memcached.openstack.svc:11212
tls_enabled=true
```

Hit ratio 99.4 %, no eviction.

**Why / how it works**: one memcached pod managed by the infrastructure
operator, listening with TLS on 11212 and in clear on 11211. Services
address each replica by its stable pod DNS name. The plain port on
localhost lets you read statistics without a TLS client. Kolla-Ansible
equivalent: `memcached` container on each controller, port 11211, no TLS
by default.

**Pitfalls**:

- The memory limit of memcached is about 9.9 GB (`-m 9932`) on a node
  with 31 GB and no pod limit: a cache that really filled up would take a
  third of the node. See [open questions](open-questions.md).
- The pod has no `nc`; use the bash `/dev/tcp` form above or
  `memcached-tool` with an explicit address and port.
- memcached holds no durable data, but emptying it sends the next token
  validations of every service back to Keystone at once.

**See also**: [Inspect service status](../operations/01-inspect-service-status.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### How do I change the configuration of one Nova service only (for example turn off its debug logging)?

**Context**: Nova is several services under one resource. On the lab
`debug=true` is rendered by default and the API log is noisy.

**How**:

**[READ-ONLY]**

```bash
oc explain openstackcontrolplane.spec.nova.template.apiServiceTemplate | grep -E '^  [a-zA-Z]'
oc get oscp openstack -o jsonpath='api=[{.spec.nova.template.apiServiceTemplate.customServiceConfig}]{"\n"}'
oc exec nova-api-0 -c nova-api-api -- grep -n -E '^debug' /etc/nova/nova.conf.d/01-nova.conf
oc logs nova-api-0 -c nova-api-log --since=5m | grep -c ' DEBUG '
```

**[CHANGE]** Rolls the `nova-api` pod only.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"nova":{"template":{"apiServiceTemplate":{"customServiceConfig":"[DEFAULT]\ndebug = false\n"}}}}}'
oc rollout status statefulset/nova-api --timeout=300s
oc wait oscp openstack --for=condition=Ready --timeout=300s
oc exec nova-api-0 -c nova-api-api -- ls /etc/nova/nova.conf.d/
```

**[CHANGE]** Revert.

```bash
oc patch oscp openstack --type=json -p \
  '[{"op":"remove","path":"/spec/nova/template/apiServiceTemplate/customServiceConfig"}]'
```

**Observed on the lab** (2026-11-12): before, five minutes of light use
gave 403 lines of which 283 DEBUG. After the patch the pod was replaced
within about 10 seconds, the directory contained `01-nova.conf` and
`02-nova-override.conf` (the two lines of the patch), and one minute of
the same use gave 14 lines, none DEBUG. Only `nova-api-0` was restarted;
scheduler, conductors and metadata kept running. The revert took 25
seconds including the return to `Ready`.

**Why / how it works**: the Nova resource has one template per service
(`apiServiceTemplate`, `schedulerServiceTemplate`,
`metadataServiceTemplate`, and under `cellTemplates` the
`conductorServiceTemplate` and `noVNCProxyServiceTemplate` of each cell), each with its own `customServiceConfig`, written as
`02-nova-override.conf` after the generated file. Kolla-Ansible
equivalent: `/etc/kolla/config/nova/nova-api.conf` and
`kolla-ansible reconfigure -t nova`.

**Pitfalls**:

- The snippet of one service template does not reach the others, and it
  does **not** reach `nova_compute` on the node (that is
  `nova-extra-config`, see [compute operations](openstack-compute.md)).
- `nova-api` is a StatefulSet with one replica on the lab: the API is
  unavailable for a few seconds during the rollout.
- A merge patch with `null` also works for the revert; the JSON patch
  `remove` fails if the field is absent, which is a useful safety in a
  script.
- The log container starts empty after a rollout: the lines from before
  the change are gone.

**See also**: [Change service configuration](../operations/04-change-service-configuration.md),
[Logs](../operations/02-logs.md),
[Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md)

### How do I give a service CPU and memory requests and limits?

**Context**: OpenStack pods run without requests or limits by default
(see [capacity and observability](openstack-capacity-and-observability.md)).
You want to protect or contain one service.

**How**:

**[READ-ONLY]**

```bash
oc explain openstackcontrolplane.spec.placement.template.resources
oc get pods -l service=placement -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,REQ:.spec.containers[*].resources.requests,LIM:.spec.containers[*].resources.limits'
```

**[CHANGE]** Rolls the Placement pod.

```bash
oc patch oscp openstack --type=merge -p \
  '{"spec":{"placement":{"template":{"resources":{"requests":{"cpu":"100m","memory":"256Mi"},"limits":{"memory":"1Gi"}}}}}}'
oc rollout status deployment/placement --timeout=300s
oc wait oscp openstack --for=condition=Ready --timeout=300s
```

**[CHANGE]** Revert.

```bash
oc patch oscp openstack --type=json -p '[{"op":"remove","path":"/spec/placement/template/resources"}]'
```

**Observed on the lab** (2026-11-12): rollout and `Ready` in 23 seconds.

```text
POD                 QOS         REQ                                                     LIM
placement-<id>      Burstable   map[cpu:100m memory:256Mi],map[cpu:100m memory:256Mi]   map[memory:1Gi],map[memory:1Gi]
```

The node summary moved from 4808m to 5008m of CPU requests and from
22431 Mi to 22943 Mi of memory requests: **twice** the values of the
patch. After the revert the pod was `BestEffort` again and the Deployment
went back to its previous ReplicaSet.

**Why / how it works**: most service templates expose a standard
Kubernetes `resources` field; the operator copies it to **every**
container of the pod (API and log sidecar here). Kolla-Ansible
equivalent: `<service>_dimensions` (for example `placement_api_dimensions`)
and `kolla-ansible reconfigure`.

**Pitfalls**:

- Because the values apply per container, the pod reserves the request
  as many times as it has containers. Divide accordingly.
- A memory limit below the real usage (see the usage table in the
  capacity file) gives `OOMKilled` restarts; start with requests only.
- Requests are subtracted from what the scheduler can place on the node.
  On a single node at 72 % of memory requested, generous requests on all
  services would leave pods `Pending`.
- Only Placement was tried. The field exists in the other templates
  (seen with `oc explain` for the Nova API and memcached) but their
  behaviour was not checked.

**See also**: [Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Scale a service](../operations/06-scale-a-service.md),
[Pod pending or CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md)

### Why do the API pods log "AMQP server is unreachable" every few minutes?

**Context**: the Nova API log shows
`AMQP server on rabbitmq-cell1.openstack.svc:5671 is unreachable: [SYS]
unknown error (_ssl.c:2501). Trying again in 1 seconds.` although
RabbitMQ is healthy.

**How**:

**[READ-ONLY]**

```bash
oc logs nova-api-0 -c nova-api-log --since=3h | grep -c 'is unreachable'
for b in rabbitmq-server-0 rabbitmq-cell1-server-0; do
  echo "$b $(oc logs $b -c rabbitmq --since=3h | grep -c 'missed heartbeats')"
  oc logs $b -c rabbitmq --since=3h | grep -B1 'missed heartbeats' | grep -o -E ' - [a-zA-Z_-]+:[0-9]+:' | sed -E 's/:[0-9]+:$//' | sort | uniq -c
done
oc exec rabbitmq-cell1-server-0 -c rabbitmq -- rabbitmqctl list_connections -q name timeout | awk '{print $NF}' | sort | uniq -c
oc exec nova-api-0 -c nova-api-api -- grep -n heartbeat /etc/nova/nova.conf.d/01-nova.conf
```

**Observed on the lab** (2026-11-12): 17 `is unreachable` lines in three
hours in the Nova API log. Over the same period the brokers closed 24
(`rabbitmq`) and 40 (`rabbitmq-cell1`) connections:

```text
closing AMQP connection (<pod-ip>:<port> -> <pod-ip>:5671 - mod_wsgi:11:<id>, duration: '3M, 0s'):
missed heartbeats from client, timeout: 60s
```

Every one of them came from a client named `mod_wsgi`; none from
schedulers, conductors or the compute node. All connections negotiate a
60-second heartbeat, and the Nova configuration has
`heartbeat_in_pthread=false`.

**Why / how it works**: services that run under Apache `mod_wsgi` (the
API pods) only send AMQP heartbeats while a request is being processed.
An idle worker stays silent, the broker closes its connection for
missed heartbeats (the closed connections had lived three minutes), and
the worker discovers it at its next use, logs the error and reconnects
within a second. No API call failed during the campaign. Long-running
services (scheduler, conductor, `nova_compute`) send their heartbeats in
the background and did not appear among the closed connections. Kolla-Ansible equivalent:
the same messages appear in `nova-api.log` when the API runs under
`mod_wsgi`.

**Pitfalls**:

- These lines count as ERROR in a log scan. Subtract them before you
  conclude that the broker is unstable; check
  `rabbitmq-diagnostics check_local_alarms` instead.
- The frequency follows API idleness, not load: a busy API logs fewer of
  them.
- Do not "fix" it by setting `heartbeat_in_pthread=true`: the generated
  file sets it to false on purpose, with a comment saying that logging
  from the heartbeat thread would cause hangs in the API image.
- A broker that is really down gives the same message, but repeated every
  second and in **all** services.

**See also**: [Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md),
[Logs](../operations/02-logs.md)

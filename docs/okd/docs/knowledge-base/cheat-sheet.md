# Cheat sheet

One-liners taken from the entries of this knowledge base, all run on the
lab on 2026-11-12. Read-only unless marked **[CHANGE]**. Run on the
bastion after `oc project openstack`.

## Helpers

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
export OS_CLIENT_CONFIG_FILE=~/kb-demo/clouds.yaml OS_CLOUD=kb-demo; o=~/kb-demo/venv/bin/openstack
compute() { ssh -i ~/okd-openstack-lab/.work/dataplane-ssh-key cloud-admin@192.168.122.100 "$@"; }
nb() { oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovn-nbctl "$@"; }
sb() { oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-sbctl "$@"; }
r() { oc exec rabbitmq-server-0 -c rabbitmq -- "$@"; }
g() { oc exec openstack-galera-0 -c galera -- mysql -e "$1"; }
nm() { oc exec nova-cell0-conductor-0 -c nova-cell0-conductor-conductor -- "$@" 2>&1 | grep -v DEBUG; }
```

## Identity and tenants

```bash
os token issue -f value -c expires
os endpoint list -c "Service Name" -c Interface -c URL
oc get route -n openstack
oc get secret rootca-public -o jsonpath='{.data.ca\.crt}' | base64 -d > ~/kb-demo/rootca-public.crt
os role assignment list --project kb-demo --project-domain kb-demo --names -f value
os quota show --usage "$(os project show kb-demo --domain kb-demo -f value -c id)"
$o catalog list -f value -c Name -c Type
```

**[CHANGE]**

```bash
os project create --domain kb-demo kb-demo
os role add --user kb-demo-member --user-domain kb-demo --project kb-demo --project-domain kb-demo member
os quota set --instances 4 --cores 4 --ram 2048 "$(os project show kb-demo --domain kb-demo -f value -c id)"
oc exec -i openstackclient -c openstackclient -- openstack image create kb-cirros-0.6.3 --public --disk-format qcow2 --container-format bare < ~/kb-demo/cirros.img
```

## Networking

```bash
os network agent list
nb show
sb show
nb get NB_Global . nb_cfg sb_cfg hv_cfg
nb list Gateway_Chassis
sb find Port_Binding type=chassisredirect
oc exec ovsdbserver-nb-0 -c ovsdbserver-nb -- ovs-appctl -t /etc/ovn/ovnnb_db.ctl cluster/status OVN_Northbound
oc exec ovn-northd-0 -c ovn-northd -- ovn-appctl -t /tmp/ovn-northd.1.ctl status
compute sudo ovs-vsctl show
compute sudo ovs-vsctl get open_vswitch . external_ids:ovn-bridge-mappings
compute sudo podman exec ovn_controller ovn-appctl -t ovn-controller connection-status
compute ip netns list
$o security group rule list kb-demo-ssh -c "IP Protocol" -c "Port Range" -c Direction -c "IP Range"
oc exec ovsdbserver-sb-0 -c ovsdbserver-sb -- ovn-trace --ct new --minimal "$LS" "inport == \"$P2\" && eth.src == $M2 && eth.dst == $M1 && ip4.src == 10.20.0.127 && ip4.dst == 10.20.0.121 && ip.ttl == 64 && tcp.dst == 22 && tcp.src == 40000"
```

**[CHANGE]**

```bash
os network create kb-public --external --provider-network-type flat --provider-physical-network datacentre
$o router set kb-demo-router --external-gateway kb-public
$o floating ip create kb-public -f value -c floating_ip_address
```

## Compute

```bash
$o server event list kb-vm1
$o server show kb-vm1 -f value -c fault
$o console log show kb-vm1 --lines 12
os compute service list -c Binary -c Host -c Zone -c Status -c State
rp=$(os resource provider list -f value -c uuid | sed -n 1p)
os resource provider inventory list $rp
os resource provider usage show $rp
os allocation candidate list --resource VCPU=1 --resource MEMORY_MB=256 -f value
os server migration list --server <instance-id>
oc logs nova-scheduler-0 --since=5m | grep -E 'Filter .* returned 0 hosts'
nm nova-manage cell_v2 list_hosts
nm nova-status upgrade check
compute sudo virsh list --all
compute 'sudo podman ps --format "{{.Names}} {{.Status}}"'
compute 'sudo podman logs --since 10m nova_compute 2>&1 | tail -5'
oc get openstackdataplanedeployment
```

**[CHANGE]**

```bash
$o server create kb-vm1 --image kb-cirros-0.6.3 --flavor kb.tiny --network kb-demo-net --key-name kb-demo-key --security-group kb-demo-ssh --wait
os compute service set --disable --disable-reason "maintenance" edpm-compute-0.ctlplane.okd.lab.example.com nova-compute
os compute service set --enable edpm-compute-0.ctlplane.okd.lab.example.com nova-compute
compute sudo systemctl restart edpm_nova_compute
$o server shelve --wait kb-vm-a
$o server unshelve --wait kb-vm-a
os resource provider inventory set $rp --amend --resource VCPU:allocation_ratio=4.0
```

## Service administration

```bash
oc get pods -o custom-columns=POD:.metadata.name,SERVICE:.metadata.labels.service,CONTAINERS:.spec.containers[*].name
oc get secrets | grep config-data
oc exec nova-api-0 -c nova-api-api -- ls /etc/nova /etc/nova/nova.conf.d
oc get oscp openstack -o jsonpath='keystone=[{.spec.keystone.template.customServiceConfig}]{"\n"}'
oc get keystoneservice,keystoneendpoint
oc get keystoneapi keystone -o jsonpath='rot={.spec.fernetRotationDays} max={.spec.fernetMaxActiveKeys}{"\n"}'
r rabbitmqctl list_queues -q name messages consumers type
r rabbitmq-diagnostics -q check_local_alarms
g "SHOW GLOBAL STATUS WHERE Variable_name IN ('wsrep_cluster_size','wsrep_cluster_status','wsrep_ready','Threads_connected');"
oc get galera,mariadbdatabase,mariadbaccount
oc get galerabackup; oc get cronjob | grep backup
oc exec memcached-0 -c memcached -- memcached-tool 127.0.0.1:11211 stats
r rabbitmqctl list_policies -q
oc logs rabbitmq-cell1-server-0 -c rabbitmq --since=3h | grep -c 'missed heartbeats'
oc get pods -l service=placement -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,REQ:.spec.containers[*].resources.requests'
```

**[CHANGE]** Each patch rolls the pods of the service; wait with
`oc wait oscp openstack --for=condition=Ready --timeout=300s`.

```bash
oc patch oscp openstack --type=merge -p '{"spec":{"keystone":{"template":{"customServiceConfig":"[DEFAULT]\ndebug = true\n"}}}}'
oc patch oscp openstack --type=merge -p '{"spec":{"keystone":{"template":{"customServiceConfig":null}}}}'
oc patch oscp openstack --type=merge -p '{"spec":{"nova":{"template":{"apiServiceTemplate":{"customServiceConfig":"[DEFAULT]\ndebug = false\n"}}}}}'
oc patch oscp openstack --type=json -p '[{"op":"remove","path":"/spec/nova/template/apiServiceTemplate/customServiceConfig"}]'
oc patch oscp openstack --type=merge -p '{"spec":{"placement":{"template":{"resources":{"requests":{"cpu":"100m","memory":"256Mi"}}}}}}'
oc patch oscp openstack --type=json -p '[{"op":"remove","path":"/spec/placement/template/resources"}]'
oc annotate keystoneendpoint placement kb1/poke="$(date +%s)" --overwrite
oc -n openstack create job --from=cronjob/backup-openstack kb1-backup-openstack
```

## Several compute nodes

Details in [Data plane scale-out, migration and scale-in](dataplane-scale-out-and-migration.md).
`osa` is `os --os-compute-api-version 2.79`; `$id` is an instance ID.

**[READ-ONLY]**

```bash
nm nova-manage cell_v2 list_hosts
os server list --all-projects --long -c Name -c Status -c Host
osa server migration list --server $id
os resource provider list -f value -c uuid -c name
nb lrp-get-gateway-chassis lrp-<router-port-id>
sb --bare --columns=chassis find port_binding type=chassisredirect
compute 'sudo ovs-vsctl --columns=name,bfd_status list interface | grep -A1 ovn-'
compute 'sudo podman logs --since 10m nova_compute 2>&1 | grep -E "Live Migration failure|libvirtError: " | tail -2'
```

**[CHANGE]**

```bash
nm nova-manage cell_v2 discover_hosts --verbose
osa server migrate --live-migration --host edpm-compute-1.ctlplane.okd.lab.example.com $id
osa server migrate $id && osa server migration confirm $id <migration-id>
osa server evacuate $id
nb lrp-set-gateway-chassis lrp-<router-port-id> <chassis-name> 3
os network agent delete <agent-id>
os compute service delete <service-id>
oc patch openstackdataplanenodeset openstack-edpm --type=json -p '[{"op":"remove","path":"/spec/nodes/edpm-compute-1"}]'
```

## Backup and restore

Details in [Backup and restore drills](backup-and-restore-drills.md).

**[READ-ONLY]**

```bash
sql() { local i=$1; shift; oc exec -c galera $i-galera-0 -- mysql -nN -e "$*"; }
oc exec -c galera openstack-galera-0 -- bash -c 'mysqldump --all-databases --single-transaction --routines --events --flush-privileges | gzip -c' > mysqldump-all-openstack.sql.gz
oc get cm openstack-backup-scripts -o jsonpath='{.data.restore_galera}'
oc exec nova-cell0-conductor-0 -- nova-manage placement audit --verbose
oc exec $(oc get pod -l service=neutron -o name | head -1) -c neutron-api -- neutron-ovn-db-sync-util --config-file /etc/neutron/neutron.conf --config-dir /etc/neutron/neutron.conf.d --ovn-neutron_sync_mode log
oc get svc openstack openstack-cell1 -o jsonpath='{range .items[*]}{.spec.selector}{"\n"}{end}'
node sudo ls -l /home/core/assets/backup/
```

**[DESTRUCTIVE]** Restore one instance from a chosen pair of files, then
repair.

```bash
printf 'apiVersion: mariadb.openstack.org/v1beta1\nkind: GaleraRestore\nmetadata: {name: cell1-restore}\nspec: {backupSource: openstack-cell1}\n' | oc apply -f -
oc wait galerarestore/cell1-restore --for=condition=Ready --timeout=5m
oc exec restore-cell1-restore -- ls -l /backup/data
oc exec restore-cell1-restore -- /var/lib/backup-scripts/restore_galera --yes /backup/data/<data-file> /backup/data/<grants-file> | tee restore.log; grep FAILED restore.log
oc delete galerarestore cell1-restore
oc exec nova-cell0-conductor-0 -- nova-manage placement audit --verbose --delete
oc exec $(oc get pod -l service=neutron -o name | head -1) -c neutron-api -- neutron-ovn-db-sync-util --config-file /etc/neutron/neutron.conf --config-dir /etc/neutron/neutron.conf.d --ovn-neutron_sync_mode repair
```

## Capacity and observability

```bash
oc adm top node
oc adm top pods -n openstack --sort-by=memory
oc get pods -n openstack -o jsonpath='{range .items[*]}{.status.qosClass}{"\n"}{end}' | sort | uniq -c
oc describe node okd-0 | sed -n '/Allocated resources/,/Events/p'
oc get events -n openstack --field-selector type=Warning --sort-by=.lastTimestamp
oc get events -A --field-selector reason=OOMKilling
q() { oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- curl -s --data-urlencode "query=$1" http://localhost:9090/api/v1/query; }
q 'increase(kube_pod_container_status_restarts_total{namespace="openstack"}[24h]) > 0'
oc logs nova-api-0 -c nova-api-log --since=30m | grep ' ERROR ' | cut -c1-200
oc logs -n openstack -l service=nova-conductor --all-containers --prefix --since=10m --tail=2
oc logs -n openstack-operators deploy/nova-operator-controller-manager --since=30m | tail -5
compute 'nproc; free -m | sed -n 2p; df -h / | sed -n 2p'
```

## OKD helpers

```bash
node() { ssh core@192.168.130.10 "$@"; }
e() { oc exec -n openshift-etcd etcd-okd-0 -c etcdctl -- "$@"; }
q() { oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- curl -s --data-urlencode "query=$1" http://localhost:9090/api/v1/query; }
am() { oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- amtool --alertmanager.url=http://localhost:9093 "$@"; }
OVNK=$(oc get pods -n openshift-ovn-kubernetes -l app=ovnkube-node -o name)
NS=openstack-operators
V=.work/idp/viewer.kubeconfig
```

## OKD cluster health and etcd

```bash
oc get clusterversion
oc adm upgrade
oc get co --no-headers | awk '$3!="True" || $4!="False" || $5!="False"'
oc get co kube-apiserver -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason} {.lastTransitionTime} {.message}{"\n"}{end}'
oc get kubeapiserver cluster -o jsonpath='{range .status.nodeStatuses[*]}{.nodeName} current={.currentRevision} target={.targetRevision} lastFailed={.lastFailedRevision}{"\n"}{end}'
node 'sudo crictl ps --name "kube-apiserver|etcd|kube-controller-manager|kube-scheduler"'
e etcdctl endpoint health -w table
e etcdctl endpoint status -w table
e etcdctl alarm list
q 'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])))'
oc get --raw '/readyz?verbose' | tail -3
oc get csr
```

## OKD node and host

```bash
oc debug node/okd-0 -q -- chroot /host sh -c 'id; hostname; cat /proc/1/comm'
node 'head -3 /etc/os-release; uname -r; sudo rpm-ostree status'
oc get mcp
oc get node okd-0 -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
node 'systemctl is-system-running; systemctl --failed --no-pager'
node 'systemctl status crio --no-pager | head -8; sudo crictl version'
node 'free -m; swapon --show | wc -l; sysctl vm.overcommit_memory vm.panic_on_oom'
node 'df -h /var; df -i /var | tail -1'
node 'sudo podman system df'
oc adm node-logs okd-0 -u kubelet --since=-10m | tail -3
node 'chronyc -n tracking | head -5; chronyc -n sources; timedatectl | grep -E "synchronized|NTP|Time zone"'
node 'journalctl --list-boots --no-pager'
```

**[CHANGE]** Cordon only stops new scheduling; do not run a real drain on a single node.

```bash
oc adm cordon okd-0
oc adm drain okd-0 --dry-run=client --ignore-daemonsets --delete-emptydir-data | awk '{print $1,$2}' | sort | uniq -c
oc adm uncordon okd-0
```

## OKD workloads and resources

```bash
oc get pods -n openstack -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,PRIO:.spec.priority,REQ:.spec.containers[*].resources.requests'
oc get node okd-0 -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
oc describe node okd-0 | sed -n '/^Capacity:/,/^System Info/p;/^Allocated resources/,/^Events/p'
oc adm top node
oc get oscp openstack -n openstack -o jsonpath='{.spec.keystone.template.resources}{"\n"}'
oc get pods -n openstack -l service=keystone -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,REQ:.spec.containers[*].resources.requests,LIM:.spec.containers[*].resources.limits'
node 'sudo journalctl -k --since "-1h" | grep -i -E "oom-kill|Killed process"'
oc get pdb -A
oc get sts,deploy -n openstack -o custom-columns='KIND:.kind,NAME:.metadata.name,REPLICAS:.spec.replicas'
oc get resourcequota,limitrange -A
```

**[CHANGE]** Each patch rolls the Keystone pod.

```bash
oc patch oscp openstack -n openstack --type=merge -p \
  '{"spec":{"keystone":{"template":{"resources":{"requests":{"cpu":"200m","memory":"512Mi"},"limits":{"memory":"1Gi"}}}}}}'
oc rollout status -n openstack deployment/keystone --timeout=120s
oc wait oscp openstack -n openstack --for=condition=Ready --timeout=120s
oc patch oscp openstack -n openstack --type=json -p '[{"op":"remove","path":"/spec/keystone/template/resources"}]'
```

## OKD networking

```bash
oc get network.config cluster -o jsonpath='{.spec.networkType} pods={.spec.clusterNetwork} services={.spec.serviceNetwork} mtu={.status.clusterNetworkMTU}{"\n"}'
node 'ip route; ip -br addr show br-ex; ip -br addr show ovn-k8s-mp0'
oc exec -n openshift-ovn-kubernetes $OVNK -c nbdb -- ovn-nbctl --no-leader-only show | grep -E '^(switch|router)'
oc exec -n openshift-ovn-kubernetes $OVNK -c ovn-controller -- ovn-appctl -t ovn-controller connection-status
oc get net-attach-def -n openstack
oc get route -n openstack -o custom-columns=NAME:.metadata.name,HOST:.spec.host,TERM:.spec.tls.termination,INSECURE:.spec.tls.insecureEdgeTerminationPolicy,SVC:.spec.to.name
dig +short api.okd.lab.example.com @192.168.130.5
oc get networkpolicy -n openstack; oc get networkpolicy -n openstack-operators
oc get ippools.whereabouts.cni.cncf.io -n openshift-multus
oc get ipaddresspool,l2advertisement -n metallb-system
oc get servicel2status -n metallb-system
compute 'sudo arping -c 2 -I eth1 172.17.0.80; sudo arping -c 2 -I eth1 172.17.0.85; ip neigh show 172.17.0.80'
```

**[CHANGE]** Removes one leaked whereabouts allocation (both objects); the `test` operation makes the patch fail on a wrong offset.

```bash
oc patch ippools.whereabouts.cni.cncf.io -n openshift-multus 172.17.0.0-24 --type json -p '[
  {"op":"test","path":"/spec/allocations/69/podref","value":"openstack/<ghost pod>"},
  {"op":"remove","path":"/spec/allocations/69"}]'
oc delete overlappingrangeipreservations.whereabouts.cni.cncf.io -n openshift-multus 172.17.0.69
```

## OKD storage

```bash
oc get sc -o custom-columns='NAME:.metadata.name,PROV:.provisioner,BIND:.volumeBindingMode,RECLAIM:.reclaimPolicy'
oc get pv -o custom-columns='NAME:.metadata.name,CAP:.spec.capacity.storage,RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase,CLAIM:.spec.claimRef.name,PATH:.spec.local.path'
oc get pvc -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,VOLUME:.spec.volumeName,REQ:.spec.resources.requests.storage,CAP:.status.capacity.storage'
oc get pv -o custom-columns='PATH:.spec.local.path,CLAIM:.spec.claimRef.name' --sort-by=.spec.local.path
node 'sudo du -sh /var/lib/openstack-lab-pv/*; sudo ls -ldZ /var/lib/openstack-lab-pv/pv01 /var/lib/openstack-lab-pv/pv10'
oc exec -n openstack openstack-galera-0 -c galera -- df -h /var/lib/mysql
node 'lsblk -o NAME,SIZE,TYPE /dev/vda; df -h /var | tail -1; df -i /var | tail -1'
oc get configs.imageregistry.operator.openshift.io cluster -o jsonpath='{.spec.managementState} {.spec.storage}{"\n"}'
oc get pods,cronjob -n openshift-image-registry
```

**[DESTRUCTIVE]** Recycles a `Released` volume by erasing its directory; print the path and check it before the `find`.

```bash
PV=local-storage-04
P=$(oc get pv $PV -o jsonpath='{.spec.local.path}'); echo "$P"
oc get pv $PV -o jsonpath='{.status.phase} {.spec.claimRef.namespace}/{.spec.claimRef.name}{"\n"}'   # must be Released
node "sudo find $P -mindepth 1 -delete"
oc patch pv $PV --type=json -p '[{"op":"remove","path":"/spec/claimRef"}]'
oc get pv $PV
```

## OKD access and security

```bash
oc whoami; oc whoami --show-server; oc config get-contexts
oc get oauth cluster -o jsonpath='{.spec}{"\n"}'; oc get users; oc get identities
oc get clusterrolebinding cluster-admin cluster-admins -o wide
oc get co authentication; oc get pods -n openshift-authentication
oc adm policy who-can patch openstackcontrolplanes.core.openstack.org -n openstack
oc get rolebinding -n openstack; oc get sa -n openstack
oc get ns openstack -o jsonpath='{.metadata.labels}{"\n"}'
oc adm policy who-can use scc anyuid -n openstack | grep serviceaccount:openstack:
oc get apiserver cluster -o jsonpath='{.spec.audit}{"\n"}'
oc adm node-logs okd-0 --path=kube-apiserver/              # audit.log + rotated files
oc --kubeconfig=$V auth can-i patch openstackcontrolplanes.core.openstack.org -n openstack
```

**[CHANGE]**

```bash
oc adm policy add-cluster-role-to-user cluster-admin ops-admin
oc adm policy add-cluster-role-to-user cluster-reader ops-viewer
oc adm policy add-role-to-user view ops-viewer -n openstack
oc delete user ops-admin; oc delete identity local:ops-admin
oc patch oauth cluster --type json -p '[{"op":"remove","path":"/spec/identityProviders"}]'
oc delete secret -n openshift-config local-htpasswd
```

## OKD monitoring and alerting

```bash
oc get co monitoring
oc adm top pods -n openshift-monitoring --no-headers | sort -k3 -n -r
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- du -sh /prometheus
q 'node_memory_MemAvailable_bytes/1024^3'                                   # memory available, GiB
q 'sum by (namespace,pod) (increase(kube_pod_container_status_restarts_total[6h])) > 0'   # restarts in 6 h
q 'node_filesystem_avail_bytes{mountpoint="/var"}/1024^3'
q 'up==0'                                                                    # scrape targets down
q 'ALERTS{alertstate="firing"}'
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- amtool --alertmanager.url=http://localhost:9093 alert query
am silence query
oc get events -A --field-selector type=Warning --sort-by=.lastTimestamp
oc get servicemonitor,podmonitor -n openstack; oc get servicemonitor,podmonitor -n openstack-operators
```

**[CHANGE]** A silence only mutes notifications and expires by itself.

```bash
SID=$(am silence add alertname=SamplesMissingTBRCredential --duration=10m --author="$USER" --comment="maintenance test")
am silence expire "$SID"
am silence add namespace=openstack --duration=1h --author="$USER" --comment="control plane change <ticket>"
```

## OLM and the OpenStack operators

```bash
oc get catalogsource -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,IMAGE:.spec.image,POLL:.spec.updateStrategy.registryPoll.interval,STATE:.status.connectionState.lastObservedState'
oc get subscription -n $NS -o custom-columns='NAME:.metadata.name,PKG:.spec.name,CHANNEL:.spec.channel,SOURCE:.spec.source,APPROVAL:.spec.installPlanApproval,INSTALLED:.status.installedCSV,STATE:.status.state'
oc get installplan -n $NS
oc get csv -n $NS
oc get openstack -n $NS
oc logs -n $NS deploy/keystone-operator-controller-manager --since=1h | tail -20
oc logs -n $NS deploy/openstack-operator-controller-manager --since=6h | grep -P '\tERROR\t' | tail
oc get lease -n $NS -o custom-columns='NAME:.metadata.name,HOLDER:.spec.holderIdentity,RENEW:.spec.renewTime,DURATION:.spec.leaseDurationSeconds,TRANSITIONS:.spec.leaseTransitions'
oc get crd -o name | grep -c 'openstack.org'
oc get jobs -n openstack -o custom-columns='NAME:.metadata.name,OK:.status.succeeded,TTL:.spec.ttlSecondsAfterFinished,OWNER:.metadata.ownerReferences[0].kind,CREATED:.metadata.creationTimestamp'
oc get cronjob -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,SCHEDULE:.spec.schedule,KEEP_OK:.spec.successfulJobsHistoryLimit,KEEP_FAILED:.spec.failedJobsHistoryLimit'
oc get openstackdataplanedeployment -n openstack
```

**[CHANGE]** Restarting an operator or changing `operatorOverrides` does not touch the running services.

```bash
oc delete pod -n $NS -l openstack.org/operator-name=keystone   # or: oc rollout restart deploy/keystone-operator-controller-manager -n $NS
oc rollout status -n $NS deploy/keystone-operator-controller-manager --timeout=120s
oc patch openstack -n openstack-operators openstack --type=merge \
  -p '{"spec":{"operatorOverrides":[{"name":"watcher","replicas":0}]}}'
oc patch openstack -n openstack-operators openstack --type=json -p '[{"op":"remove","path":"/spec/operatorOverrides"}]'
```

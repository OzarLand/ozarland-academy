---
template: journey.html
title: Your learning journey
description: "A guided path for beginners through the Kolla-Ansible 2024.1 study: five stages, from the conventions to the findings, progress kept in your browser."
tags: [learning, beginner]
challenges:
  discover:
    - q: "A cloud deployed by 2023.1 never set <code>om_enable_rabbitmq_quorum_queues</code>. Why does its first 2024.1 run restart the messaging services, computes included, with no operator change?"
      options: ["Because 2024.1 recreates every container to move RabbitMQ to a new image", "Because the default is now <code>true</code>, which writes <code>rabbit_quorum_queue = true</code> into the service configs: a changed file, so a restart", "Because <code>prechecks</code> converts the classic queues and then restarts the services"]
      answer: 1
      explain: "<code>om_enable_rabbitmq_quorum_queues</code> now defaults to <code>true</code> and writes <code>rabbit_quorum_queue = true</code> into 26 templates of 24 roles, nova-cell's <code>nova.conf</code> included, so those services restart <span class=\"ev ev-code\">CODE</span>. <code>prechecks</code> changes nothing: it fails while classic queues exist. Settle the queue type before that run."
      see: "start/ten-things-to-know/"
    - q: "Where do the notified restart handlers of most roles run, and which role deliberately waits?"
      options: ["At the <code>meta: flush_handlers</code> at the end of the role's <code>deploy.yml</code> (or else at the end of the play); the loadbalancer role defers to the end of its play", "Right after each task that notifies them, in every role", "Only at the very end of the whole <code>site.yml</code> run, after the last play"]
      answer: 0
      explain: "<code>meta: flush_handlers</code> is where the notified restart handlers run: at the end of most <code>deploy.yml</code> (e.g. nova's), or else at the end of the play. The loadbalancer role (haproxy, keepalived, proxysql) deliberately defers to the end of its play <span class=\"ev ev-code\">CODE</span>."
      see: "reference/glossary/"
    - q: "Which command is classed <code>read-only</code> on the operation pages, and on what is that based?"
      options: ["<code>genconfig</code>, because it restarts no container", "<code>pull</code>, because running containers do not change", "<code>prechecks</code>: the task files it reaches only read state (<code>wait_for</code>, <code>assert</code>, <code>stat</code>, container facts, and commands such as the new RabbitMQ queue listing)"]
      answer: 2
      explain: "<code>read-only</code> is supported only by <code>prechecks</code> (<code>kolla_action=precheck</code>): its task files use only checks and commands that read state, such as <code>{{ kolla_container_engine }} --version</code> or the new RabbitMQ queue listing <span class=\"ev ev-code\">CODE</span>. <code>genconfig</code> is <code>writes-config</code> and <code>pull</code> is <code>pulls-images</code>."
      see: "start/conventions/#operation-impact-classes"
    - q: "A service uses <code>config_strategy</code> <code>COPY_ONCE</code> instead of the default <code>COPY_ALWAYS</code>. What does the restart handler do when its config has changed?"
      options: ["It restarts the systemd unit, and <code>kolla_set_configs</code> copies the new config at that start", "It always recreates the container: under <code>COPY_ONCE</code> the config is copied only at the first start, so only a recreate re-applies it", "It sends <code>SIGHUP</code> so that the service reloads its files"]
      answer: 1
      explain: "Under <code>COPY_ONCE</code>, <code>kolla_set_configs</code> copies the config only at the first start of a container, and the restart handler then always recreates the container, with Docker or Podman, so only a recreate re-applies config <span class=\"ev ev-code\">CODE</span>."
      see: "reference/glossary/"
    - q: "During an incident, what can the portal tell you, and what mostly not?"
      options: ["What Kolla will do given the inputs (tasks and restarts); what that does to VMs and APIs depends on the environment and is mostly <span class=\"ev ev-na\">NOT AVAILABLE</span>", "What happened to your VMs during the last run, because the study observed real runs", "Nothing: the study only covers initial deployment, not incidents"]
      answer: 0
      explain: "The portal can tell what Kolla will do given the inputs: tasks and restarts. What that does to VMs and APIs depends on the environment and is mostly <span class=\"ev ev-na\">NOT AVAILABLE</span> in these sources: no run was used as evidence."
      see: "start/find-it-fast/#start-from-a-situation"
  understand:
    - q: "You set <code>kolla_max_fail_percentage: 30</code> and run <code>reconfigure</code> with <code>ANSIBLE_SERIAL=4</code>. One host fails in each of the first three batches. Does the play stop?"
      options: ["Yes: three failed hosts against a batch of four is 75%, above 30%", "No: ansible-core compares the hosts failed in the current batch with the batch size (1 of 4, 25%, each time); the failed list is cleared at each batch", "No: <code>max_fail_percentage</code> is ignored whenever <code>serial</code> is set"]
      answer: 1
      explain: "New in 2024.1, every play sets <code>max_fail_percentage</code> (default 100, which never stops a play early). ansible-core 2.16.20 compares the hosts failed in the current batch with the batch size and clears the failed-host list at the start of each batch, so failures do not add up across batches <span class=\"ev ev-code\">CODE</span>."
      see: "concepts/deployment-execution-flow/#5-batching-serial-and-its-interaction-with-order"
    - q: "With <code>enable_etcd</code>, an etcd config change is applied by <code>reconfigure</code>. Which member do the 2024.1 handlers restart last?"
      options: ["The leader: the handlers look up the leader, restart the non-leaders, then the leader, whose handler is defined last", "The first host of the <code>etcd</code> group, because <code>run_once</code> targets it", "The last host of the inventory, because batches follow inventory order"]
      answer: 0
      explain: "<code>Restart etcd container</code> is now only a name that handlers listen to: they look up the leader, restart the non-leaders, then the leader, which comes last because its handler is defined last; each restart waits for the client port and <code>etcdctl endpoint health</code> <span class=\"ev ev-code\">CODE</span>. Whether the <code>% 4</code> groups of non-leaders really restart one after another is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      see: "concepts/deployment-execution-flow/#7-dependencies-introduced-by-handlers"
    - q: "In 2024.1, what does the systemd unit <code>kolla-&lt;name&gt;-container.service</code> of a container say about the engine?"
      options: ["Nothing: it always calls <code>docker</code>, and Podman containers have no unit", "It names the engine: <code>ExecStart</code> and <code>ExecStop</code> call <code>/usr/bin/&lt;engine&gt;</code>, and <code>After</code>/<code>Wants</code> is <code>docker.service</code> for Docker, <code>network-online.target</code> for Podman", "It only holds the restart policy; start and stop go through the engine API"]
      answer: 1
      explain: "Changed in 2024.1: the unit template names its engine and writes <code>StartLimitInterval=</code> where 2023.1 wrote <code>StartLimitIntervalSec=</code>; with Docker the engine lines read as the 2023.1 ones (that template hard-coded <code>docker</code>), so the start-limit line is what differs. Because <code>compare_container</code> compares the whole unit text, a unit written by 2023.1 is reported as changed, and the handler restarts the container after rewriting the unit (F16) <span class=\"ev ev-code\">CODE</span>."
      see: "concepts/repository-architecture/#6-custom-modules--container-lifecycle-via-kolla_container"
    - q: "You change only the <code>command</code> in a service's <code>config.json</code>. Later its container restarts for another reason, under <code>COPY_ALWAYS</code>. Is the new command used?"
      options: ["No: the command is fixed when the container is created", "Only if <code>kolla_set_configs --check</code> reported the change first", "Yes: every start re-copies the listed entries and rewrites <code>/run_command</code>, so a changed command applies at that restart"]
      answer: 2
      explain: "A <code>COPY_ALWAYS</code> restart re-copies the listed entries and rewrites <code>/run_command</code>: changed or added files, mode and owner changes and a changed command apply <span class=\"ev ev-code\">CODE</span>. The check itself never compares <code>command</code>, so only a restart for another reason applies it."
      see: "concepts/kolla-images/#35-what-a-restart-applies"
    - q: "Why does a no-change <code>-t nova reconfigure</code> still cost a lot of work on a large fleet?"
      options: ["Because Kolla has no \"only if changed\" short-circuit at play level: every compute runs the full per-host chain", "Because every task restarts the nova containers to be safe", "Because the image of every compute is pulled again"]
      answer: 0
      explain: "Still holds in 2024.1: every run that includes the <code>compute</code> group executes the full per-host chain on every compute, even with no change: config re-rendering and comparison, container config checks, sysctl and modules, discovery <span class=\"ev ev-code\">CODE</span>. Nothing restarts, and the work is still paid on every host."
      see: "concepts/compute-scaling-and-performance/#5-why-a-small-change-becomes-a-large-workload"
  practise:
    - q: "Before the first 2024.1 run on a cloud deployed by 2023.1, why run <code>kolla-ansible prechecks</code> without <code>-t</code>?"
      options: ["Because the HA/quorum check is in the untagged <code>prechecks</code> play, and the queue-type check in the rabbitmq precheck, which runs only under the <code>rabbitmq</code> and <code>rabbitmq-ha-precheck</code> tags: a run tagged with other services skips both", "Because a tagged <code>prechecks</code> restarts the tagged services", "Because <code>-t</code> makes <code>prechecks</code> migrate the queues"]
      answer: 0
      explain: "The check that fails when <code>om_enable_rabbitmq_high_availability</code> and <code>om_enable_rabbitmq_quorum_queues</code> are equal is in the <code>prechecks</code> role, an untagged play that any tagged run skips (<code>roles/prechecks/tasks/service_checks.yml:67-72</code>). The assertion that every queue except <code>reply_</code> and <code>_fanout</code> ones is a quorum queue is in <code>roles/rabbitmq/tasks/precheck.yml</code>, under the <code>rabbitmq</code> and <code>rabbitmq-ha-precheck</code> tags, so a run tagged with other services skips it too <span class=\"ev ev-code\">CODE</span>."
      see: "operations/pre-execution-checklist/#2-first-20241-run-on-a-cloud-deployed-by-20231"
    - q: "Before the first 2024.1 run, how can you list on a host the containers that will restart because of the changed systemd unit text (F16)?"
      options: ["<code>kolla_set_configs --check</code> in each container: exit 1 marks them", "<code>grep -l StartLimitIntervalSec /etc/systemd/system/kolla-*-container.service</code>: the 2024.1 template has no such key, so each listed unit differs from it", "<code>kolla-ansible genconfig</code>, then a diff of <code>/etc/kolla/</code>"]
      answer: 1
      explain: "The 2024.1 template writes <code>StartLimitInterval=</code> and compares the whole unit file, so each unit still holding <code>StartLimitIntervalSec=</code> is drift <span class=\"ev ev-code\">CODE</span>. <code>kolla_set_configs --check</code> does not show it, and the unit is not under <code>/etc/kolla/</code>."
      see: "operations/predict-a-run/#2-the-first-20241-run-on-a-cloud-deployed-by-20231"
    - q: "You run <code>ANSIBLE_SERIAL=1 kolla-ansible -i multinode -t nova reconfigure</code> with the three <code>multinode</code> controllers. How many times do <code>nova_api_bootstrap</code> (API DB sync) and <code>nova_cell_bootstrap</code> (cell DB sync) run?"
      options: ["Once each: both are <code>run_once</code>", "Three times each: every controller runs both", "3 and 1: the API DB sync is <code>run_once</code> in a controller play batched one host at a time; the cell DB sync is gated on the first nova-conductor"]
      answer: 2
      explain: "A <code>run_once</code> task runs once per batch of its own play, so with <code>kolla_serial=1</code> the API DB sync runs once per controller. The cell DB sync is not <code>run_once</code>: it is gated on the first nova-conductor and runs once at any serial value <span class=\"ev ev-code\">CODE</span>."
      see: "operations/controlled-batches/#12-rolling-reconfigure-with-ansible_serial"
    - q: "With <code>haproxy_single_external_frontend: true</code> (new in 2024.1, default <code>false</code>), what does <code>-t keystone reconfigure</code> write on the loadbalancer hosts besides keystone's <code>services.d</code> file?"
      options: ["Keystone's block of <code>external-frontend-map</code>, which also notifies the HAProxy restart", "Nothing more: the single frontend is written only by <code>-t haproxy</code>", "The HAProxy configuration of every service"]
      answer: 0
      explain: "The service's loadbalancer include imports <code>loadbalancer-config</code> with <code>tags: always</code>; new in 2024.1, with <code>haproxy_single_external_frontend</code> the service's block of <code>external-frontend-map</code> is also written and also notifies the restart <span class=\"ev ev-code\">CODE</span>. <code>--skip-tags haproxy</code> drops the whole loadbalancer play."
      see: "operations/reconfigure-a-service/#2-execute-a-service-specific-tag-implicit-effects"
    - q: "You run <code>-t rabbitmq reconfigure</code> on a cloud whose RabbitMQ is already running. Which one-shot container can it start?"
      options: ["<code>rabbitmq_bootstrap</code>, on every RabbitMQ host", "None: RabbitMQ has no one-shot containers", "<code>rabbitmq_version_check</code>, on the first RabbitMQ host when the container exists; <code>rabbitmq_bootstrap</code> only for a new volume"]
      answer: 2
      explain: "The quick lookup row for <code>-t rabbitmq reconfigure</code>: <code>rabbitmq_version_check</code> runs on the first RabbitMQ host when the container exists, and <code>rabbitmq_bootstrap</code> only for a new volume; the brokers restart one by one with <code>serial: \"33%\"</code>, each node drained first <span class=\"ev ev-code\">CODE</span>."
      see: "operations/command-quick-lookup/"
  judge:
    - q: "You set a new <code>enable_*</code> flag in <code>globals.yml</code> and run <code>reconfigure -t &lt;svc&gt;</code> for that service only. What happens to common's cron logrotate config?"
      options: ["It is updated on every host, because every service play runs <code>common</code>", "It is updated on the hosts of that service only", "It stays stale until <code>-t common</code> or an untagged run"]
      answer: 2
      explain: "Common's cron logrotate config lists services by their <code>enable_*</code> flags <span class=\"ev ev-code\">CODE</span>. Still holds in 2024.1: only the <code>common</code> play renders it, and that play is tagged <code>common</code> only, so enabling a service with <code>-t &lt;svc&gt;</code> leaves it stale until <code>-t common</code> or an untagged run."
      see: "risk/tags/#4-practical-consequences"
    - q: "You want one nova-compute option on one compute only. Which override file reaches that compute only in 2024.1?"
      options: ["<code>/etc/kolla/config/nova/nova-compute.conf</code>", "<code>/etc/kolla/config/nova/&lt;host&gt;/nova-compute.conf</code>, new in 2024.1, merged into that host's <code>nova-compute/nova.conf</code> only", "<code>/etc/kolla/config/global.conf</code>, which is read per host"]
      answer: 1
      explain: "<code>nova/nova-compute.conf</code> targets every compute. New in 2024.1, the same option in <code>nova/&lt;host&gt;/nova-compute.conf</code> is merged into that host's <code>nova-compute/nova.conf</code> only <span class=\"ev ev-code\">CODE</span>."
      see: "risk/small-change-large-workload/"
    - q: "You want to keep classic RabbitMQ queues on 2024.1. Which setting is the only one that passes <code>prechecks</code>?"
      options: ["<code>om_enable_rabbitmq_high_availability: true</code> with quorum queues off and the <code>ha-all</code> policy in place", "Both flags set to <code>false</code>, the 2023.1 defaults", "Both flags set to <code>true</code>"]
      answer: 0
      explain: "This is R27 <span class=\"ev ev-code\">CODE</span>: <code>prechecks</code> fails when HA and quorum are equal (both off or both on), and with quorum on it asserts that the queues are quorum queues. The only classic-queue setting that passes is HA on, quorum off, with the <code>ha-all</code> policy in place; on a cloud that kept the 2023.1 default (HA off), 2023.1 runs removed that policy, so this path too is a manual migration, to mirrored queues, as the HA precheck message says. What oslo.messaging does with existing classic queues is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      see: "risk/risk-register/#r27"
    - q: "A cloud has <code>enable_octavia: yes</code>, the default amphora provider and <code>enable_redis</code> left at <code>no</code>. What does 2024.1 do?"
      options: ["It deploys Redis automatically for the Octavia jobboard", "Nothing changes: the jobboard is off by default", "<code>prechecks</code> fails (\"Redis must be enabled when using octavia jobboard\"); <code>deploy</code>, <code>reconfigure</code> and <code>upgrade</code> do not run that assert and render the jobboard section anyway"]
      answer: 2
      explain: "This is R30 <span class=\"ev ev-code\">CODE</span>: <code>enable_octavia_jobboard</code> is on by default with the amphora provider, so <code>octavia.conf</code> lists the <code>redis</code> group as jobboard hosts. How Octavia behaves when they hold no Redis is <span class=\"ev ev-na\">NOT AVAILABLE</span>. Choose <code>enable_redis: yes</code> or <code>enable_octavia_jobboard: no</code> before the upgrade."
      see: "risk/risk-register/#r30"
    - q: "You turn <code>haproxy_single_external_frontend</code> on, then off again. What happens to <code>services.d/external-frontend.cfg</code>?"
      options: ["It is removed at the next <code>-t haproxy reconfigure</code>", "It stays in place: <code>services.d</code> files are never removed (the only removal is <code>mariadb.cfg</code> when ProxySQL is enabled)", "It is removed by <code>genconfig</code>"]
      answer: 1
      explain: "Stale <code>services.d</code> files are never removed, and new in 2024.1, turning <code>haproxy_single_external_frontend</code> off leaves <code>services.d/external-frontend.cfg</code> in place; a disabled service's block also stays in <code>external-frontend-map</code> <span class=\"ev ev-code\">CODE</span>."
      see: "troubleshooting/known-bugs-and-limitations/"
  master:
    - q: "On a fresh cloud where Keystone was never deployed, you run <code>kolla-ansible deploy -t nova</code>. What happens?"
      options: ["Kolla deploys Keystone first, because the nova role declares a dependency on it", "Nothing enforces a dependency when you use tags: the run reaches Keystone registration with no Keystone deployed", "Nova waits until Keystone is deployed by a later run, then registers itself"]
      answer: 1
      explain: "<code>--tags</code> filters plays, and no role has a <code>meta</code> directory in 2024.1, so <code>-t nova</code> on a fresh cloud reaches Keystone registration (<code>service-ks-register</code>, against <code>keystone_internal_url</code>) with no Keystone deployed <span class=\"ev ev-code\">CODE</span>."
      see: "components/dependencies/#6-deployment-order-vs-runtime-dependency"
    - q: "During an <code>upgrade</code> with <code>nova_safety_upgrade: yes</code>, which nova containers keep running?"
      options: ["<code>nova_compute</code>, <code>nova_compute_ironic</code>, <code>nova_libvirt</code> and <code>nova_ssh</code>; the API, scheduler, conductors and console proxies stay down until the reload plays start them again", "None: every nova container is stopped first", "Only the API services, so that users see no outage"]
      answer: 0
      explain: "<code>nova_safety_upgrade</code> stops <code>nova_api</code>, <code>nova_scheduler</code>, <code>nova_super_conductor</code> and, on the cell hosts, the conductor and console proxies before the upgrade; the compute-side containers keep running and their restart handlers are not skipped <span class=\"ev ev-code\">CODE</span>."
      see: "components/nova-deep-dive/#7-upgrade-path-specifics"
    - q: "You run <code>kolla-ansible deploy</code> with <code>--limit</code> set to one new compute host. Why does work still run on <code>control01</code>?"
      options: ["Because <code>--limit</code> is ignored by every play that includes the <code>compute</code> group", "It does not: <code>--limit</code> confines every action to the hosts you name", "Because <code>delegate_to: groups[x][0]</code> runs work on hosts outside the limit: the Neutron DB create/grant, the <code>bootstrap_neutron</code> container and cell discovery"]
      answer: 2
      explain: "Still holds in 2024.1 (F8): <code>--limit</code> does not confine actions <span class=\"ev ev-code\">CODE</span>. With a compute host as the limit, <code>control01</code> runs the Neutron DB create/grant, the <code>bootstrap_neutron</code> container and cell discovery, so \"only the new compute\" still executes DB-sync containers on a controller."
      see: "reference/findings/#f8"
    - q: "Kolla-Ansible 2024.1 also accepts ansible-core 2.15. If you run it with 2.15, do the study's statements about Ansible behaviour (loop-notify, <code>run_once</code> with <code>serial</code>, <code>max_fail_percentage</code>) still hold?"
      options: ["Yes: the study validated them with lab runs on both versions", "Not established: only ansible-core 2.16.20 was read, so the behaviour of 2.15 is not available", "No: the study shows that 2.15 has no loop-notify"]
      answer: 1
      explain: "Only one ansible-core version was read: Kolla-Ansible 2024.1 accepts 2.15 to 2.16, and the behaviour of 2.15 is <span class=\"ev ev-na\">NOT AVAILABLE</span>. The study rests only on reading source code, with no runtime or lab evidence."
      see: "reference/method-and-limits/#limits-of-this-study"
    - q: "New in 2024.1, the openvswitch post-config also sets <code>external_ids:hostname</code>, and a change of it notifies the <code>openvswitch_vswitchd</code> restart. Does the first 2024.1 run restart <code>openvswitch_vswitchd</code> on every compute?"
      options: ["Yes, always, because the key is new", "No, never, because post-config runs only on new hosts", "Not established: whether the run reports the new key as changed depends on the <code>openvswitch_db</code> module, whose code is not in the studied sources"]
      answer: 2
      explain: "The notify is <span class=\"ev ev-code\">CODE</span>, but whether the first 2024.1 run reports <code>external_ids:hostname</code> changed, and so restarts <code>openvswitch_vswitchd</code>, is <span class=\"ev ev-na\">NOT AVAILABLE</span>: the <code>openvswitch_db</code> module is not in these sources."
      see: "troubleshooting/what-is-not-known/#network-data-plane"
---

# Your learning journey

New to Kolla-Ansible Day-2 operations? Follow these five stages in order. Each stage groups a few pages of this study,
from the easiest to the most detailed. You do not need to read everything at once: come back whenever you like.

<img src="../assets/images/S3-start.webp" width="1536" height="1024" loading="lazy" alt="LUMO holds up a parchment while Ilyan lays out an open book, scrolls and blank index cards on a reading table.">

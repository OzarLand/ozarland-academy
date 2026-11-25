---
template: journey.html
title: Your learning journey
description: "A guided path for beginners through the Kolla-Ansible 2025.1 study: five stages, from the conventions to the findings, progress kept in your browser."
tags: [learning, beginner]
challenges:
  discover:
    - q: "You change one setting of <code>nova_compute</code> only. In 2025.1, which containers does the next <code>-t nova reconfigure</code> restart on a compute?"
      options: ["<code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code>, as in 2024.1", "<code>nova_compute</code> only: the shared check step notifies only the containers it found changed", "None: config changes are reloaded"]
      answer: 1
      explain: "Changed in 2025.1: the config tasks no longer notify handlers; <code>service-check-containers</code> compares each container and notifies only those that changed, so loop-notify is gone <span class=\"ev ev-code\">CODE</span>."
      see: "start/ten-things-to-know/"
    - q: "Where do the notified restart handlers of most roles run, and which role deliberately waits?"
      options: ["At the <code>meta: flush_handlers</code> at the end of the role's <code>deploy.yml</code> (or else at the end of the play); the loadbalancer role defers to the end of its play", "Right after each task that notifies them, in every role", "Only at the very end of the whole <code>site.yml</code> run, after the last play"]
      answer: 0
      explain: "<code>meta: flush_handlers</code> is where the notified restart handlers run: at the end of most <code>deploy.yml</code> (e.g. nova's), or else at the end of the play. The loadbalancer role (haproxy, keepalived, proxysql) defers to the final check of its play <span class=\"ev ev-code\">CODE</span>."
      see: "reference/glossary/"
    - q: "Which command is classed <code>read-only</code> on the operation pages?"
      options: ["<code>genconfig</code>, because it restarts no container", "<code>pull</code>, because running containers do not change", "<code>prechecks</code>: the task files it reaches only read state"]
      answer: 2
      explain: "<code>read-only</code> is supported only by <code>prechecks</code> (<code>kolla_action=precheck</code>): its task files use only checks and commands that read state <span class=\"ev ev-code\">CODE</span>. <code>genconfig</code> is <code>writes-config</code> and <code>pull</code> is <code>pulls-images</code>."
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
    - q: "You set <code>kolla_max_fail_percentage: 30</code> and run <code>deploy -e kolla_serial=4</code>. One host fails in each of the first three batches. Does the play stop?"
      options: ["Yes: three failed hosts against a batch of four is 75%, above 30%", "No: ansible-core compares the hosts failed in the current batch with the batch size (1 of 4, 25%, each time); the failed list is cleared at each batch", "No: <code>max_fail_percentage</code> is ignored whenever <code>serial</code> is set"]
      answer: 1
      explain: "Every play sets <code>max_fail_percentage</code> (default 100, which never stops a play early). ansible-core 2.18.20 compares the hosts failed in the current batch with the batch size and clears the failed-host list at the start of each batch, so failures do not add up across batches <span class=\"ev ev-code\">CODE</span>."
      see: "concepts/deployment-execution-flow/#5-batching-serial-and-its-interaction-with-order"
    - q: "Why does <code>reconfigure -e kolla_serial=4</code> restart a service on every host at once in 2025.1?"
      options: ["Because <code>reconfigure</code> puts <code>kolla_serial=0</code> into its own extra vars, after yours, so 0 wins", "Because <code>kolla_serial</code> is only read from <code>globals.yml</code>", "It does not: it restarts four hosts at a time"]
      answer: 0
      explain: "F19 <span class=\"ev ev-code\">CODE</span>: the Python CLI's <code>Reconfigure</code> and <code>Upgrade</code> set <code>kolla_serial</code> to the constant <code>ANSIBLE_SERIAL = 0</code> after the operator's options. <code>deploy -e kolla_serial=4</code> runs the same tasks in batches of four."
      see: "operations/controlled-batches/#12-rolling-runs-with-kolla_serial-not-with-reconfigure"
    - q: "In 2025.1, what changed in the systemd unit <code>kolla-&lt;name&gt;-container.service</code>, and why does it matter on the first run?"
      options: ["Nothing changed", "The template adds <code>PartOf=kolla.target</code>; the whole unit text is compared, so a unit written by 2024.1 counts as drift and its container restarts", "The unit now reloads the service instead of restarting it"]
      answer: 1
      explain: "F16 <span class=\"ev ev-code\">CODE</span>: <code>compare_container</code> compares the whole unit text, so the first 2025.1 check of a container whose unit 2024.1 wrote reports a change, and the handler restarts it after rewriting the unit."
      see: "concepts/repository-architecture/#6-custom-modules--container-lifecycle-via-kolla_container"
    - q: "You change only the <code>command</code> in a service's <code>config.json</code> and run <code>genconfig</code>, then <code>deploy-containers</code>. Is the new command applied?"
      options: ["No: the check never compares the command", "Yes: in 2025.1 <code>kolla_set_configs --check</code> reports a command that differs from <code>/run_command</code>, so the container restarts", "Only after a host reboot"]
      answer: 1
      explain: "Changed in 2025.1 (F14) <span class=\"ev ev-code\">CODE</span>: kolla's <code>set_configs.py</code> now compares the running command, saved in <code>/run_command</code>, with the <code>command</code> of <code>config.json</code>. A change confined to <code>permissions</code> is still not detected."
      see: "concepts/kolla-images/#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes"
    - q: "Why does a no-change <code>-t nova reconfigure</code> still cost a lot of work on a large fleet?"
      options: ["Because Kolla has no \"only if changed\" short-circuit at play level: every compute runs the full per-host chain", "Because every task restarts the nova containers to be safe", "Because the image of every compute is pulled again"]
      answer: 0
      explain: "Still holds in 2025.1: every run that includes the <code>compute</code> group executes the full per-host chain on every compute, even with no change; new in 2025.1, each compute also lists the hypervisors through the first conductor (F20) <span class=\"ev ev-code\">CODE</span>."
      see: "concepts/compute-scaling-and-performance/#5-why-a-small-change-becomes-a-large-workload"
  practise:
    - q: "You run <code>deploy -t keystone</code> after a change to the keystone frontend. What do you run to make HAProxy load it?"
      options: ["Nothing: the same run restarts HAProxy", "<code>-t haproxy</code> (or <code>-t loadbalancer</code>, or a run without tags): the service tag only writes the frontend file", "<code>genconfig -t haproxy</code>"]
      answer: 1
      explain: "F18 <span class=\"ev ev-code\">CODE</span>: the HAProxy restart comes only from the loadbalancer play's final check, which runs with <code>-t haproxy</code>, <code>-t loadbalancer</code>, <code>-t keepalived</code> or no tag. Until then the change stays pending, and any such run applies it."
      see: "operations/reconfigure-a-service/#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
    - q: "Before the first 2025.1 run, how can you list on a host the containers that will restart because of the changed systemd unit text (F16)?"
      options: ["<code>kolla_set_configs --check</code> in each container: exit 1 marks them", "<code>grep -L PartOf=kolla.target /etc/systemd/system/kolla-*-container.service</code>: each unit without that line differs from the 2025.1 template", "<code>kolla-ansible genconfig</code>, then a diff of <code>/etc/kolla/</code>"]
      answer: 1
      explain: "The 2025.1 template adds <code>PartOf=kolla.target</code> and the whole unit file is compared, so each unit without that line is drift <span class=\"ev ev-code\">CODE</span>. <code>kolla_set_configs --check</code> does not show it, and the unit is not under <code>/etc/kolla/</code>."
      see: "operations/predict-a-run/#2-the-first-20251-run-on-a-cloud-deployed-by-20241"
    - q: "You run <code>kolla-ansible deploy -i multinode -t nova -e kolla_serial=1</code> with the three <code>multinode</code> controllers. How many times does the <code>run_once</code> API DB sync run?"
      options: ["Once: it is <code>run_once</code>", "Three times: a <code>run_once</code> task runs once per batch of its play, and each batch is one controller", "Never: DB sync runs only on <code>upgrade</code>"]
      answer: 1
      explain: "A <code>run_once</code> task runs once per batch of its own play (F10), so with <code>kolla_serial=1</code> the API DB sync runs once per controller <span class=\"ev ev-code\">CODE</span>."
      see: "risk/tags/#25-run_once-with-serial-code"
    - q: "An entry disappears from a container's <code>config.json</code>, for example an optional file that is no longer rendered. What do the next runs do?"
      options: ["Nothing: a dropped entry is never noticed", "They restart that container on every run until it is recreated: the check keeps reporting the dropped entry", "They remove the file and stop reporting drift"]
      answer: 1
      explain: "New in 2025.1 (F21) <span class=\"ev ev-code\">CODE</span>: nothing removes the recorded destination from the container's defaults state, so the check fires on every run until the container is recreated. Whether removing the container is a safe way out is <span class=\"ev ev-na\">NOT AVAILABLE</span> (Q23)."
      see: "reference/findings/#f21"
  judge:
    - q: "You set a new <code>enable_*</code> flag in <code>globals.yml</code> and run <code>reconfigure -t &lt;svc&gt;</code> for that service only. What happens to common's cron logrotate config?"
      options: ["It is updated on every host, because every service play runs <code>common</code>", "It is updated on the hosts of that service only", "It stays stale until <code>-t common</code> or an untagged run"]
      answer: 2
      explain: "Common's cron logrotate config lists services by their <code>enable_*</code> flags <span class=\"ev ev-code\">CODE</span>. Only the <code>common</code> play renders it, and that play is tagged <code>common</code> only, so enabling a service with <code>-t &lt;svc&gt;</code> leaves it stale until <code>-t common</code> or an untagged run."
      see: "risk/tags/#4-practical-consequences"
    - q: "A 2024.1 cloud still has classic RabbitMQ queues. What does the 2025.1 code allow?"
      options: ["Keeping them with <code>om_enable_rabbitmq_high_availability</code>", "Nothing else than quorum queues: the classic queues must be migrated before the first 2025.1 run", "Converting them during the first run"]
      answer: 1
      explain: "F17, R27 <span class=\"ev ev-code\">CODE</span>: quorum queues are the only choice in 2025.1. What oslo.messaging does with existing classic queues, and how long a manual migration takes, is <span class=\"ev ev-na\">NOT AVAILABLE</span> (Q16)."
      see: "risk/risk-register/#r27"
    - q: "A cloud has <code>enable_octavia: yes</code>, the default amphora provider, and neither Redis nor Valkey enabled. What does 2025.1 do?"
      options: ["It deploys Valkey automatically for the Octavia jobboard", "Nothing changes: the jobboard is off by default", "<code>prechecks</code> fails; <code>deploy</code>, <code>reconfigure</code> and <code>upgrade</code> do not run that assert and render the jobboard section anyway"]
      answer: 2
      explain: "This is R30 <span class=\"ev ev-code\">CODE</span>: <code>enable_octavia_jobboard</code> is on by default with the amphora provider, so <code>octavia.conf</code> lists the <code>valkey</code> hosts, or else the <code>redis</code> hosts, as jobboard backend. How Octavia behaves when they hold neither is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      see: "risk/risk-register/#r30"
    - q: "You want to move a cloud from Docker to Podman with <code>kolla-ansible migrate-container-engine</code>. What does the code do?"
      options: ["It moves one host at a time and asks for confirmation", "It works on every host in one play, asks for no confirmation, and stops every container of the old engine before moving the volumes", "It only changes <code>globals.yml</code>"]
      answer: 1
      explain: "This is R31 <span class=\"ev ev-code\">CODE</span>: the blast radius is the whole cloud, with <code>nova_libvirt</code> and Open vSwitch stopped on every compute at once; the effect on guests is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      see: "risk/risk-register/#r31"
  master:
    - q: "On a fresh cloud where Keystone was never deployed, you run <code>kolla-ansible deploy -t nova</code>. What happens?"
      options: ["Kolla deploys Keystone first, because the nova role declares a dependency on it", "Nothing enforces a dependency when you use tags: the run reaches Keystone registration with no Keystone deployed", "Nova waits until Keystone is deployed by a later run, then registers itself"]
      answer: 1
      explain: "<code>--tags</code> filters plays, and no role has a <code>meta</code> directory, so <code>-t nova</code> on a fresh cloud reaches Keystone registration (<code>service-ks-register</code>) with no Keystone deployed <span class=\"ev ev-code\">CODE</span>."
      see: "components/dependencies/#6-deployment-order-vs-runtime-dependency"
    - q: "You run <code>kolla-ansible deploy</code> with <code>--limit</code> set to one new compute host. Why does work still run on <code>control01</code>?"
      options: ["Because <code>--limit</code> is ignored by every play that includes the <code>compute</code> group", "It does not: <code>--limit</code> confines every action to the hosts you name", "Because <code>delegate_to: groups[x][0]</code> runs work on hosts outside the limit: the Neutron DB create/grant, the <code>bootstrap_neutron</code> container, cell discovery and, new in 2025.1, the hypervisor list"]
      answer: 2
      explain: "Still holds in 2025.1 (F8): <code>--limit</code> does not confine actions <span class=\"ev ev-code\">CODE</span>. \"Only the new compute\" still executes DB-sync containers on a controller."
      see: "reference/findings/#f8"
    - q: "Kolla-Ansible 2025.1 also accepts ansible-core 2.17. If you run it with 2.17, do the study's statements about Ansible behaviour (<code>run_once</code> with <code>serial</code>, <code>max_fail_percentage</code>) still hold?"
      options: ["Yes: the study validated them with lab runs on both versions", "Not established: only ansible-core 2.18.20 was read, so the behaviour of 2.17 is not available", "No: the study shows that 2.17 behaves differently"]
      answer: 1
      explain: "Only one ansible-core version was read: Kolla-Ansible 2025.1 accepts 2.17 to 2.18, and the behaviour of 2.17 is <span class=\"ev ev-na\">NOT AVAILABLE</span>. The study rests only on reading source code, with no runtime or lab evidence."
      see: "reference/method-and-limits/#limits-of-this-study"
    - q: "Does a <code>nova_libvirt</code> restart keep the guests' console logs?"
      options: ["Yes, always", "No, never", "Not established: the console output now goes through a virtlogd that runs in that container, and libvirt, QEMU and virtlogd are not in these sources"]
      answer: 2
      explain: "This is Q22, new in 2025.1: <span class=\"ev ev-na\">NOT AVAILABLE</span>, left for the community to confirm."
      see: "troubleshooting/open-questions/#q22"
---

# Your learning journey

New to Kolla-Ansible Day-2 operations? Follow these five stages in order. Each stage groups a few pages of this study,
from the easiest to the most detailed. You do not need to read everything at once: come back whenever you like.

<img src="../assets/images/S3-start.webp" width="1536" height="1024" loading="lazy" alt="LUMO holds up a parchment while Ilyan lays out an open book, scrolls and blank index cards on a reading table.">

## Where this journey starts

This study reads the sources of one tag, Kolla-Ansible 2025.1. It describes what the move to 2025.1 does to a cloud
that 2024.1 deployed, so several quiz items, and the "first 2025.1 run" items of [Ten things to
know](ten-things-to-know.md), start from such a cloud. If your first cloud is new, for example the 2026.1 lab of the
Academy's [Quick lab](../../../lab/variants/openstack-cloud/), you have no 2024.1 cloud and no earlier run to compare
with: those items are not about your cloud, and the study does not cover 2026.1.

You can still learn from it. The five stages teach how Kolla-Ansible is built and how a command becomes tasks,
restarts and risks. Start with [Conventions](conventions.md) to read the evidence labels. Then read
[Repository architecture](../concepts/repository-architecture.md) and [Deployment execution
flow](../concepts/deployment-execution-flow.md). Skip the "cloud deployed by 2024.1" parts on a first pass.

Every statement here is code read in the 2025.1 sources, so the study gives no timings and no observed behaviour; what
a lab run has not confirmed is left for the community to confirm. The lab page gives the timings that were measured on
2026.1 ([Quick lab](../../../lab/variants/openstack-cloud/), section "Releases"). Treat them as a different release,
not as 2025.1 evidence.

---
template: journey.html
title: Your learning journey
description: "A guided path for beginners: five stages, from the conventions of the pages to the detailed findings, with your progress kept in your browser."
tags: [learning, beginner]
challenges:
  discover:
    - q: "You change one global setting on the deployment host, for example a RabbitMQ or memcached membership or a password. Why can this small central change restart containers across the whole fleet?"
      options: ["Because Kolla-Ansible restarts every container after any change, whatever it is", "Because global settings land in per-host files, including compute-side configs", "Because the change is copied to the hosts only by a full <code>pull</code> of the images"]
      answer: 1
      explain: "Global settings land in per-host files: <code>enable_*</code>, RabbitMQ/memcached membership and passwords end up in compute-side configs, so small central changes cause fleet-wide restarts."
      see: "start/ten-things-to-know/"
    - q: "You rebuilt an image and pushed it under the same tag, then ran <code>deploy</code>. The containers still run the old image. Why?"
      options: ["<code>deploy</code> never pulls an image that is already present; rebuilt images under the same tag need <code>pull</code>", "<code>deploy</code> pulled the image but only <code>reconfigure</code> recreates containers", "<code>deploy</code> skips every image whose tag is unchanged until <code>genconfig</code> has run"]
      answer: 0
      explain: "<code>deploy</code> never pulls an image that is already present. Rebuilt images under the same tag need <code>pull</code>."
      see: "start/ten-things-to-know/"
    - q: "A service uses <code>config_strategy</code> <code>COPY_ONCE</code> instead of the default <code>COPY_ALWAYS</code>. What happens to a config change when its container is only restarted?"
      options: ["It is applied, because <code>kolla_set_configs</code> copies the config on every container start", "It is applied by a reload, without stopping the container", "It is not re-applied: under <code>COPY_ONCE</code> the config is copied only on the first start, so only a recreate re-applies it"]
      answer: 2
      explain: "<code>COPY_ALWAYS</code>, the default, copies the config and applies permissions on every container start. <code>COPY_ONCE</code> does it only on the first start of a container, so only a recreate re-applies config <span class=\"ev ev-code\">CODE</span>."
      see: "reference/glossary/"
    - q: "An operation page shows the impact class <code>restarts-on-drift</code> under its title. What does that tell you?"
      options: ["Every command of the page restarts all containers of the service", "At least one command of the page can restart containers, only if drift is detected", "The command renders config and restarts no Docker container"]
      answer: 1
      explain: "<code>restarts-on-drift</code> means the command can restart containers, only if drift is detected. A class says that at least one command of the page has that impact, not that all do; \"renders config and restarts no Docker container\" is <code>writes-config</code>."
      see: "start/conventions/#operation-impact-classes"
    - q: "During an incident, what can the portal tell you, and what mostly not?"
      options: ["What Kolla will do given the inputs (tasks and restarts); what that does to VMs and APIs depends on the environment and is mostly <span class=\"ev ev-na\">NOT AVAILABLE</span>", "What happened to your VMs during the last run, because the study observed real runs", "Nothing: the study only covers initial deployment, not incidents"]
      answer: 0
      explain: "During an incident, the portal can tell what Kolla will do given the inputs: tasks and restarts. What that does to VMs and APIs depends on the environment and is mostly <span class=\"ev ev-na\">NOT AVAILABLE</span> in these sources."
      see: "start/find-it-fast/#start-from-a-situation"
  understand:
    - q: "<code>globals.yml</code> sets a variable, and you set a different value for one host in the inventory <code>host_vars</code>. Which value does that host get, and why?"
      options: ["The <code>globals.yml</code> value: it is passed as extra-vars, the highest precedence in Ansible", "The <code>host_vars</code> value: per-host settings always win over global ones", "The <code>group_vars/all.yml</code> default: it is read last"]
      answer: 0
      explain: "<code>globals.yml</code> is passed with <code>-e @file</code>, which is extra-vars, so a value in <code>globals.yml</code> cannot be overridden per host or per group in the inventory <span class=\"ev ev-code\">CODE</span>. Per-host variation must come from variables that are not set in <code>globals.yml</code>."
      see: "concepts/repository-architecture/#21-variable-precedence-that-matters"
    - q: "With <code>kolla_serial</code> set, the nova-cell play runs batch by batch over the computes. When are the neutron agents on compute001 restarted?"
      options: ["Right after compute001's own batch finishes the nova-cell play", "Only after all computes have finished the nova-cell and openvswitch plays", "Never: batching skips the handlers"]
      answer: 1
      explain: "A batch runs the complete play, handler restarts included, before the next batch starts, but each play is still traversed batch by batch for the whole fleet before the next play starts."
      see: "concepts/deployment-execution-flow/#5-batching-serial-and-its-interaction-with-order"
    - q: "All of memcached's settings are in the <code>command</code> of its <code>config.json</code> (<code>\"config_files\": []</code>). Why does <code>kolla_set_configs --check</code> never make a memcached setting change restart the container?"
      options: ["Because memcached has no systemd unit to compare", "Because <code>--check</code> compares <code>command</code> only for one-shot containers", "Because <code>--check</code> iterates only <code>config_files</code>, so this manifest always returns 0"]
      answer: 2
      explain: "<code>--check</code> never compares <code>config.json</code>'s <code>command</code> and <code>permissions</code>: it iterates only <code>config_files</code>, so a manifest with <code>\"config_files\": []</code>, like memcached's, always returns 0."
      see: "concepts/kolla-images/#32-what-is-never-compared"
    - q: "Why does a no-change <code>-t nova reconfigure</code> still cost a lot of work on a large fleet?"
      options: ["Because Kolla has no \"only if changed\" short-circuit at play level: every compute runs the full per-host chain", "Because every task restarts the nova containers to be safe", "Because the image of every compute is pulled again"]
      answer: 0
      explain: "Every run that includes the <code>compute</code> group executes the full per-host chain on every compute, even with no change: config re-rendering and comparison, container config checks, common role (in untagged runs), sysctl and modules, OVS post-config, discovery. Nothing restarts, and yet at 500 computes the run still costs about 13,000 remote invocations."
      see: "concepts/compute-scaling-and-performance/#5-why-a-small-change-becomes-a-large-workload"
    - q: "Why is restarting a container enough to apply a changed or added config file?"
      options: ["Because the service watches its files and reloads them", "Because with <code>COPY_ALWAYS</code>, <code>kolla_set_configs</code> copies the files listed in <code>config.json</code> at every container start", "Because the restart handler pulls a new image"]
      answer: 1
      explain: "The <code>config.json</code> manifest tells <code>kolla_set_configs</code> which files to copy from <code>/var/lib/kolla/config_files</code>; with <code>config_strategy: COPY_ALWAYS</code> the copy happens at every container start. That is why Kolla-Ansible never applies config by reloading a service."
      see: "concepts/repository-architecture/#7-configuration-generation-and-overrides"
  practise:
    - q: "You change only the <code>command</code> of memcached in its <code>config.json</code> (for example its <code>-m</code> option), run <code>genconfig</code>, then <code>kolla_set_configs --check</code> as root in the memcached container. What happens?"
      options: ["It exits 0: <code>command</code> is not compared and memcached has an empty <code>config_files</code>, so the change is not seen as drift", "It exits 1: any change to <code>config.json</code> is drift and the next run restarts memcached", "It exits 2: the check fails the task on that host"]
      answer: 0
      explain: "0 = every file listed in <code>config_files</code> matches its live copy; <code>command</code> and <code>permissions</code> are not compared, so memcached (<code>\"config_files\": []</code>) always returns 0 <span class=\"ev ev-code\">CODE</span>. Such drift takes effect only at the next restart for another reason."
      see: "operations/predict-a-run/"
    - q: "You run <code>ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure</code>. How often does compute discovery run?"
      options: ["Once for the whole run, because it is <code>run_once</code>", "On the first compute of each nova-cell batch, so once per batch that contains computes", "Never: discovery is skipped when <code>serial</code> is set"]
      answer: 1
      explain: "A <code>run_once</code> task runs once per batch of its own play; compute discovery runs on the first compute of each nova-cell batch, so it repeats once per batch that contains computes <span class=\"ev ev-code\">CODE</span>."
      see: "operations/controlled-batches/#12-rolling-reconfigure-with-ansible_serial"
    - q: "In 2023.1, does <code>kolla-ansible -t keystone reconfigure</code> also check and possibly restart the <code>common</code> containers (fluentd, kolla_toolbox, cron) on the keystone hosts?"
      options: ["Yes: <code>common</code> is a meta dependency of every role and inherits the tag", "Yes, but only on the loadbalancer hosts", "No: <code>common</code> is its own play, tagged <code>common</code> only, so it runs only under <code>-t common</code> or a run without tags"]
      answer: 2
      explain: "No role has a <code>meta/</code> directory; <code>common</code> is a separate play with <code>tags: common</code>, so a service tag never touches the <code>common</code> containers in 2023.1."
      see: "operations/reconfigure-a-service/#2-execute-a-service-specific-tag-implicit-effects"
    - q: "In 2023.1, does <code>-t neutron reconfigure</code> run the one-shot <code>bootstrap_neutron</code> container (<code>neutron-db-manage upgrade head</code>)?"
      options: ["No, never: the neutron DB sync is deploy-only", "Yes: it runs on every deploy and reconfigure, whatever <code>neutron_enable_rolling_upgrade</code>", "Only when <code>neutron_enable_rolling_upgrade</code> is <code>no</code>"]
      answer: 1
      explain: "The quick lookup table says that in 2023.1 <code>bootstrap_neutron</code> runs on every deploy and reconfigure, whatever <code>neutron_enable_rolling_upgrade</code>; the untagged <code>reconfigure</code> runs the db sync of every enabled service, neutron included."
      see: "operations/command-quick-lookup/"
    - q: "Step 1 of the checklist runs <code>kolla-ansible genconfig</code> with the same tags and <code>--limit</code> before the real run. Why can it be run safely?"
      options: ["It writes config but restarts no Docker container: every container restart handler has <code>when: kolla_action != \"config\"</code>", "It writes nothing: it only prints the config it would render", "It restarts containers, but only one host at a time"]
      answer: 0
      explain: "genconfig writes config but does not restart any Docker container; the handlers without that guard are no-ops, chained steps, or steps genconfig never notifies. The Ussuri nova-hyperv exception no longer exists in 2023.1. Then you diff <code>/etc/kolla/&lt;service&gt;/</code>."
      see: "operations/pre-execution-checklist/"
  judge:
    - q: "You add one extra controller to the inventory. Why is this small change a large workload?"
      options: ["It changes the transport URL in every messaging service everywhere", "Only the new controller gets containers; the rest of the cloud is untouched", "Only HAProxy restarts, to add the new backend"]
      answer: 0
      explain: "One extra controller changes the transport URL in every messaging service everywhere, so the change reaches far beyond the new host."
      see: "risk/small-change-large-workload/"
    - q: "A config change concerns only one container of a role. Why can every container of that role on that host restart?"
      options: ["Because Kolla restarts every container of a host after any config change", "Because the loop result is changed if any item changed, and then the handler of every executed item is notified", "Because the handlers of a role are tagged with the role name"]
      answer: 1
      explain: "Loop notify: if any item changed, the templated handler name of every executed item is notified, so a change that concerns one container restarts every container of that role on that host <span class=\"ev ev-code\">CODE</span>. Skipped items do not notify."
      see: "risk/tags/#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code"
    - q: "You set a new <code>enable_*</code> flag in <code>globals.yml</code> and run <code>reconfigure -t &lt;svc&gt;</code> for that service only. What happens to common's cron logrotate config?"
      options: ["It is updated on every host, because every service play runs <code>common</code>", "It is updated on the hosts of that service only", "It stays stale until <code>-t common</code> or an untagged run"]
      answer: 2
      explain: "Common's cron logrotate config lists services by their <code>enable_*</code> flags <span class=\"ev ev-code\">CODE</span>. Since only the common play renders it, enabling a service with <code>-t &lt;svc&gt;</code> leaves the logrotate config stale until <code>-t common</code> or an untagged run."
      see: "risk/tags/#4-practical-consequences"
    - q: "A service image is rebuilt and pushed under the same tag. You run <code>reconfigure</code> without <code>pull</code>. What happens?"
      options: ["The containers of that service are recreated with the new image", "Nothing changes: only absent images are pulled, and the comparison uses the local image of that tag", "The run fails because the image digests differ"]
      answer: 1
      explain: "This is R13 <span class=\"ev ev-code\">CODE</span>: nothing changes (only absent images are pulled; the comparison uses the local image of that tag). After <code>pull</code>: recreate, plus loop-notify restarts. Precautions: use immutable tags; always <code>pull</code> deliberately."
      see: "risk/risk-register/#r13--rebuilt-image-under-the-same-tag-then-deployreconfigure-without-pull"
    - q: "You change only the <code>command</code> in a container's <code>config.json</code>, then run <code>genconfig</code> + <code>deploy-containers</code>. Is the change applied?"
      options: ["No: <code>kolla_set_configs --check</code> compares only <code>config_files</code> entries, so the change is not applied until the container restarts for another reason", "Yes: <code>kolla_set_configs --check</code> detects it and the container restarts", "Yes, but only on the first host of the group"]
      answer: 0
      explain: "<code>kolla_set_configs --check</code> compares only <code>config_files</code> entries: changes confined to <code>config.json</code> (<code>command</code>, <code>permissions</code>) are never detected, so neither <code>genconfig</code> + <code>deploy-containers</code> nor a later run applies them until the container restarts for another reason <span class=\"ev ev-code\">CODE</span>."
      see: "troubleshooting/known-bugs-and-limitations/"
  master:
    - q: "On a fresh cloud where Keystone was never deployed, you run <code>kolla-ansible deploy -t nova</code>. What happens?"
      options: ["Kolla deploys Keystone first, because the nova role declares a dependency on it", "The run fails at Keystone registration: nothing enforces a dependency when you use tags", "Nova deploys fine and registers itself in Keystone later, once Keystone is deployed"]
      answer: 1
      explain: "Nothing enforces a dependency when you use tags: <code>--tags</code> filters plays, and <code>-t nova</code> on a fresh cloud fails at Keystone registration if Keystone was never deployed <span class=\"ev ev-code\">CODE</span>. Kolla-Ansible never declares inter-service dependencies explicitly: in 2023.1 no role has a <code>meta</code> directory."
      see: "components/dependencies/#6-deployment-order-vs-runtime-dependency"
    - q: "You set <code>enable_barbican: yes</code>. The flag changes <code>nova.conf</code> and also <code>common</code>'s fluentd and cron files. Does a nova run restart <code>cron</code>, <code>fluentd</code> and <code>kolla_toolbox</code> on the nova hosts?"
      options: ["No: the nova roles have no <code>meta/</code>, so a nova run does not touch them; they restart only when the <code>common</code> play runs", "Yes: <code>common</code> is a meta dependency of nova, so its container check restarts them on every nova host", "Yes, but only on the computes, through loop-notify of the <code>nova_compute</code> handler"]
      answer: 0
      explain: "In 2023.1 <code>common</code> is its own play tagged <code>common</code> and the nova roles have no <code>meta/</code> (no role dependency), so a nova run does not touch <code>cron</code>, <code>fluentd</code> or <code>kolla_toolbox</code>; an untagged or <code>-t common</code> run restarts them on every host of the <code>common</code> play <span class=\"ev ev-code\">CODE</span>."
      see: "components/nova-deep-dive/#23-configuration-dependencies-inputs-that-change-novas-files"
    - q: "You run <code>kolla-ansible deploy</code> with <code>--limit</code> set to one new compute host. Why does work still run on <code>control01</code>?"
      options: ["Because <code>--limit</code> is ignored by every play that includes the <code>compute</code> group", "It does not: <code>--limit</code> confines every action to the hosts you name", "Because <code>delegate_to: groups[x][0]</code> runs work on hosts outside the limit: the Neutron DB create/grant, the <code>bootstrap_neutron</code> container and cell discovery"]
      answer: 2
      explain: "<code>--limit</code> does not confine actions: <code>delegate_to: groups[x][0]</code> runs work on hosts outside the limit <span class=\"ev ev-code\">CODE</span>. With <code>deploy --limit</code> set to a compute host, <code>control01</code> runs the Neutron DB create/grant and the <code>bootstrap_neutron</code> container, plus cell discovery, so \"only the new compute\" still executes DB-sync containers on a controller."
      see: "reference/findings/#f8"
    - q: "With <code>enable_neutron_agent_ha: yes</code>, the L3 agent wrapper runs <code>neutron-netns-cleanup --force --agent-type l3</code> before the agent starts. What is established about the routers on that node when <code>neutron_l3_agent</code> restarts?"
      options: ["They keep north-south and floating-IP traffic, because the namespaces persist across the restart", "Nothing: whether they lose north-south and floating-IP connectivity until rebuilt, and whether HA routers fail over, is not established", "They always lose all traffic until an operator rebuilds them by hand"]
      answer: 1
      explain: "The cleanup at start is <span class=\"ev ev-code\">CODE</span>, but whether with the cleanup the routers on that node lose north-south and floating-IP connectivity until rebuilt, and whether HA routers fail over, is <span class=\"ev ev-na\">NOT AVAILABLE</span>. What <code>neutron-netns-cleanup</code> itself does is neutron code."
      see: "troubleshooting/what-is-not-known/#network-data-plane"
    - q: "Kolla-Ansible 2023.1 also accepts ansible-core 2.13. If you run it with 2.13, do the study's statements about Ansible behaviour (loop-notify, tags, <code>run_once</code> with <code>serial</code>) still hold?"
      options: ["Not established: only ansible-core 2.14.18 was read, so the behaviour of 2.13 is not available", "Yes: the study validated them with lab runs on both versions", "No: the study shows that 2.13 has no loop-notify"]
      answer: 0
      explain: "Only one ansible-core version was read: Kolla-Ansible 2023.1 also accepts ansible-core 2.13 (<code>tools/kolla-ansible:10-11</code>), and its behaviour is <span class=\"ev ev-na\">NOT AVAILABLE</span>. The study rests only on reading source code, with no runtime or lab evidence."
      see: "reference/method-and-limits/#limits-of-this-study"
---

# Your learning journey

New to Kolla-Ansible Day-2 operations? Follow these five stages in order. Each stage groups a few pages of this study,
from the easiest to the most detailed. You do not need to read everything at once: come back whenever you like.

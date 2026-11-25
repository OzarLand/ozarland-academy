---
title: Ansible listings
description: "ansible-core 2.18.20's own parse of the unmodified Kolla-Ansible 2025.1-eom playbooks: the --list-tags and --list-tasks listings and their limits."
tags: [tags, evidence]
---

# Ansible listings

These two files are ansible-core 2.18.20's own parse of the unmodified Kolla-Ansible `2025.1-eom` playbooks (commit
`7222f0f`), produced with the `multinode` example inventory, Kolla-Ansible 2025.1 installed in the virtual environment
and ansible-collection-kolla `2025.1-eom` (commit `09189c7`) on the collections path. They list what the playbooks
contain; nothing was executed against a host. They replace the ansible-core 2.16.20 listings of the 2024.1 study,
which do not carry over.

| File | Command (from the kolla-ansible checkout, multinode inventory) |
|---|---|
| [list-tags-site.txt](list-tags-site.txt) | `ansible-playbook -i ansible/inventory/multinode ansible/site.yml --list-tags` |
| [list-tasks-nova.txt](list-tasks-nova.txt) | `ansible-playbook -i ansible/inventory/multinode ansible/site.yml --list-tasks -t nova` |

The commands call `ansible-playbook` directly. **Changed in 2025.1:** the `kolla-ansible` CLI has no way to pass
`--list-tags`, and its own `-lt`/`--list-tasks` option says in its help that it "has no affect on kolla-ansible"
(`kolla_ansible/ansible.py:88-94`), so the listings cannot be produced through it.

Limits of these listings, read from the playbooks ([Tags
§2.6](../../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)): every service role is reached through a
dynamic `include_tasks` (or, in the loadbalancer play, a dynamic `include_role`), so the listings show the plays and the
include tasks, not the tasks inside the included files. In `list-tasks-nova.txt` the `Apply role nova` and `Apply role
nova-cell` plays show one `include_tasks` each, and the loadbalancer play two `include_role` lines. Tags set only inside
dynamic includes do not appear in `--list-tags`: `service-rabbitmq` (`roles/service-rabbitmq/tasks/main.yml:44-45`) and
`service-images-pull` (`roles/service-images-pull/tasks/main.yml:17-18`) are in neither file. Both files start with
`Could not match supplied host pattern` warnings for the groups that only `group_by` (`site.yml:15-74`) or the handlers
create at run time, such as `enable_nova_True`, `mariadb_restart` and `rabbitmq_restart`.

What the listings show that changed since 2024.1:

- **Play order:** in `list-tasks-nova.txt` the ten Nova plays are plays #37 to #46, after the `openvswitch`,
  `ovs-dpdk`, `ovn-controller` and `ovn-db` plays (#33 to #36); see [Repository architecture
  §3](../../concepts/repository-architecture.md#3-anatomy-of-siteyml).
- **Plays added and removed:** `Apply role valkey` is play #12 and the `swift` play is gone; the total is still 71
  plays.
- The order of the tags inside one `TAGS: [...]` list is not stable from one run to the next (the loadbalancer play
  prints `haproxy`, `keepalived` and `loadbalancer` in a different order in the two files); only the set of tags
  carries meaning.

## Related

- [Tags §2.6](../../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code) — why `--list-tasks` is not usable for
  Kolla
- [Technical findings](../findings.md) — [F7](../findings.md#f7): `--list-tasks` cannot show what a tag runs
- [Predict and inspect a run](../../operations/predict-a-run.md) — `genconfig` and `kolla_set_configs --check` to see
  what will restart before a run
- [Method and limits of the study](../method-and-limits.md) — the validation phase that produced the listings

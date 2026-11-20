---
title: Ansible listings
description: "ansible-core 2.14.18's own parse of the unmodified Kolla-Ansible 2023.1-eol playbooks: the --list-tags and --list-tasks listings and their limits."
tags: [tags, evidence]
---

# Ansible listings

These two files are ansible-core 2.14.18's own parse of the unmodified Kolla-Ansible `2023.1-eol` playbooks, produced
with the `multinode` example inventory, Kolla-Ansible 2023.1 installed in the virtual environment and
ansible-collection-kolla on the collections path. They list what the playbooks contain; nothing was executed against a
host. They replace the Ansible 2.9.27 listings of the Ussuri study, which do not carry over.

| File | Command (from the kolla-ansible checkout, multinode inventory) |
|---|---|
| [list-tags-site.txt](list-tags-site.txt) | `ansible-playbook -i <inventory> ansible/site.yml --list-tags` |
| [list-tasks-nova.txt](list-tasks-nova.txt) | `ansible-playbook -i <inventory> ansible/site.yml --list-tasks -t nova` |

Limits of these listings, read from the playbooks ([Tags
§2.6](../../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)): every service role is reached through a
dynamic `include_tasks` (or, in the loadbalancer play, a dynamic `include_role`), so the listings show the plays and the
include tasks, not the tasks inside the included files. In `list-tasks-nova.txt` the `Apply role nova` and `Apply role
nova-cell` plays show one `include_tasks` each, and the loadbalancer play two `include_role` lines. Tags set only inside
dynamic includes do not appear in `--list-tags`: `service-rabbitmq` (`roles/service-rabbitmq/tasks/main.yml:46-47`) is
in neither file. Both files start with `Could not match supplied host pattern` warnings for the groups that only
`group_by` (`site.yml:16-20`) or the handlers create at run time, such as `enable_nova_True`, `mariadb_restart` and
`rabbitmq_restart`.

## Related

- [Tags §2.6](../../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code) — why `--list-tasks` is not usable for
  Kolla
- [Technical findings](../findings.md) — [F7](../findings.md#f7): `--list-tasks` cannot show what a tag runs
- [Predict and inspect a run](../../operations/predict-a-run.md) — `genconfig` and `kolla_set_configs --check` to see
  what will restart before a run
- [Method and limits of the study](../method-and-limits.md) — the validation phase that produced the listings

---
title: Swift
description: Kolla Ansible 2025.1 no longer deploys Swift. What the removal leaves on a cloud upgraded from 2024.1, and what to decide before the upgrade.
tags: [swift, upgrade, dependencies, unknowns]
---

# Swift

**Removed in 2025.1** [CODE]. Kolla Ansible 2025.1 no longer has a `swift` role: the release note says "Support for
deploying ``Swift`` has been removed" (release note `remove-swift-5ebd7b5c4a2cb5b7.yaml`), there is no swift play in
`site.yml` and no `ansible/roles/swift/` directory, `enable_swift` is no longer defined in `group_vars/all.yml`, and
kolla 2025.1 builds no swift image (no `docker/swift*` directory). The `swift` tag selects no play any more
([Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row "removed
services"). The 2024.1 study of the role is in the [2024.1 Swift page](../../2024.1/components/swift/).

This page lists what the sources show about a cloud that ran Swift under Kolla Ansible 2024.1 and is upgraded to
2025.1, and what they do not show.

## What the removal does not clean up

No 2025.1 task looks at a deployed Swift [CODE]:

- **No precheck.** No task under `ansible/roles/` tests `enable_swift`, and `prechecks` has no swift check (grep for
  `swift` under `roles/prechecks/` and in `group_vars/all.yml`: no match). Leaving `enable_swift: yes` in
  `globals.yml` does nothing and raises no error.
- **No stop, no removal.** The 15 to 18 swift containers of 2024.1 (`swift_proxy_server`, `swift_rsyncd`, the
  account, container and object servers) are not stopped or removed by any 2025.1 action, since no play targets them
  ([Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row "removed
  services"). They keep running on their 2024.1 images.
- **The HAProxy frontends stay.** The `haproxy-config` role writes `services.d/<name>.cfg` only for the services of
  the role it runs for, and removes nothing (`roles/haproxy-config/tasks/main.yml:2-21`); the haproxy `config.json`
  copies the whole `services.d/` directory (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:17-18`). The
  `swift_api` and `swift_api_external` files written by 2024.1 are therefore still served after an upgrade, pointing at
  the old proxy servers, until the operator deletes them.
- **The Keystone service and endpoints stay.** 2024.1 registered a `swift` service of type `object-store`; no 2025.1
  task removes it.
- **Logging:** the `common` role no longer lists swift for fluentd or logrotate; its template
  `roles/common/templates/cron-logrotate-swift.conf.j2` is still in the tree but no task uses it (grep of
  `roles/common/tasks/`).

## Who loses their Swift backend

- **Glance:** the `swift` store is removed with no check. On a cloud whose only store was Swift, the first 2025.1 run
  makes `file` the default store, on the first `glance-api` host only ([Glance](glance.md), "Changed in 2025.1").
- **Cinder backup:** the Swift backup driver branch is gone from `cinder.conf` ([Cinder](cinder.md)); with
  `cinder_backup_driver: swift`, no `backup_driver` line is written.
- **Horizon:** the Swift settings are removed from `_9998-kolla-settings.py` ([Horizon](horizon.md)).

## Before upgrading a cloud that runs Swift

- Decide where the object data and the Glance images go before the upgrade, not after: the sources give no migration
  path. Kolla Ansible 2025.1 still integrates an external Ceph RadosGW, whose `ceph-rgw` role registers a Keystone
  service with the same name and type, `swift` / `object-store` (`roles/ceph-rgw/defaults/main.yml:74-80`).
- Set the Glance and Cinder backup backends explicitly for 2025.1, and plan the removal of the swift containers, the
  two HAProxy frontend files and the Keystone service as manual steps.

## Not known

- [NOT AVAILABLE] What Glance does with images whose locations point at the removed `swift` store; whether the old
  swift containers keep serving correctly once HAProxy and the rest of the control plane are on 2025.1; what the
  `ceph-rgw` registration does to an existing `swift` service's endpoints. To be confirmed by the community.

## Related

- [Glance](glance.md) — the silent switch to the `file` store
- [Cinder](cinder.md) — the Swift backup driver is gone
- [HAProxy and keepalived](haproxy-keepalived.md) — frontends are not removed when a service disappears
- [Tags](../risk/tags.md) — the `swift` tag selects nothing in 2025.1
- [Components](index.md) — the other component pages

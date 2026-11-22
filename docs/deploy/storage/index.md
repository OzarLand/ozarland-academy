---
title: "storage"
description: "Storage designs and their trade-offs for Glance, Cinder and Nova: what is shared, what is local, what each choice implies."
---

# storage

Storage designs and their trade-offs for Glance, Cinder and Nova: what is shared, what is local, what each choice implies. Add a page with [`templates/deployment-pattern.md`](https://github.com/OzarLand/ozarland-academy/blob/main/docs/deploy/templates/deployment-pattern.md) (the shared [deployment pattern template](https://github.com/OzarLand/ozarland/blob/main/community/templates/deployment-pattern.md)).

<img src="../assets/images/S2-networking-and-storage.webp" width="1536" height="1024" loading="lazy" alt="LUMO stands between two tables: on one, a water model with brass paths linking small piers; on the other, blocks, cylinders and crates of different materials.">

The status of each page is its front matter `status`; see the [repository README](../index.md#-how-much-each-page-was-checked) for what each status means.

| Page | Status |
|---|---|
| [Cinder and Glance back-ends compared. LVM, Ceph RBD and NFS, and what each choice implies](cinder-and-glance-backends-compared-lvm-ceph-nfs.md) | `draft` |
| [Where instance disks live. Local on each compute, in Ceph RBD, or boot from volume, and what each choice means for migration, evacuation and capacity](nova-instance-disks-local-ceph-rbd-or-boot-from-volume.md) | `draft` |

---
title: "Upgrade journeys"
description: "Evidence-based paths to bring a legacy OpenStack cloud back to a current release, starting with Kolla-Ansible Ussuri to 2026.1."
---

# 🧭 Upgrade journeys

**Bringing legacy OpenStack clouds back to a modern release, safely and with evidence.**

[The gap](#-the-gap) · [Method](#-how-a-journey-works) · [Results](#-ussuri--20261-what-the-lab-showed) ·
[Journeys](#-journeys) · [Validation rules](docs/validation-status.md) · [Contribute](#-contributing)

Many production clouds still run OpenStack releases that went out of maintenance years ago. This module builds open,
evidence-based paths to bring them back to a current release without losing a single VM, volume, network or user.
The first journey takes a Kolla-Ansible Ussuri cloud (2020) to OpenStack 2026.1.

> [!NOTE]
> **Status: lab experiments.** The database fast-forward is lab-verified; nothing is production-validated yet.
> The investigation was written with AI agents, under the direction of the OzarLand owner (see
> [Contributing](#-contributing)).

## 🚀 The gap

Upstream upgrades one release at a time, or one SLURP step. From Ussuri that is nine upgrades and three host OS
changes before a maintained release, so many clouds stay where they are. This project looks for a safer, shorter way,
in the open, with evidence.

```mermaid
flowchart LR
    U["Ussuri<br/>2020"] --> V[Victoria] --> W[Wallaby] --> X[Xena] --> Y[Yoga] --> Z[Zed] --> A["2023.1"]
    A --> C["2024.1"] --> E["2025.1"] --> G["2026.1"]
    U -. "the question:<br/>one journey?" .-> G
    classDef old fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef mid fill:#f3f4f6,stroke:#9ca3af,color:#111827
    classDef new fill:#dcfce7,stroke:#16a34a,color:#14532d
    class U old
    class V,W,X,Y,Z,A,C,E mid
    class G new
```

## 🔄 How a journey works

```mermaid
flowchart LR
    I["🔍 Investigate<br/>upstream sources,<br/>compatibility matrix"] --> P["📐 Propose<br/>strategies and<br/>experiments"]
    P --> R["🛡️ Red team<br/>challenges before<br/>anything runs"]
    R --> L["🧪 Lab<br/>copies of a preserved<br/>baseline, frozen criteria"]
    L --> R2["🛡️ Red team<br/>challenges the<br/>results"]
    R2 --> D["📘 Runbook<br/>only from what<br/>passed, status on<br/>every step"]
    L -. "failed runs are<br/>published too" .-> D
    classDef neutral fill:#f3f4f6,stroke:#9ca3af,color:#111827
    classDef red fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef lab fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef go fill:#dcfce7,stroke:#16a34a,color:#14532d
    class I,P neutral
    class R,R2 red
    class L lab
    class D go
```

## 🔬 Ussuri → 2026.1: what the lab showed

The databases of every service reach 2026.1 **without deploying any intermediate release**: the migration code of a
few releases runs offline, on copies, with the services stopped. 2026.1 then starts on the result and operates every
pre-existing resource. Lab-verified on a container lab with synthetic data; **unsupported upstream; not for
production.**

```mermaid
flowchart LR
    subgraph stop["Control plane stopped, computes fenced"]
      U["Ussuri DBs<br/>MariaDB 10.3"] -->|"2023.1 code<br/>bridge to Alembic"| H1["2023.1"]
      H1 -->|"Cinder 23.5.0 only<br/>(use_quota fix)"| H1b["2023.2"]
      H1b -->|"2024.1 code"| H2["2024.1"] -->|"2025.1 code"| H3["2025.1"] -->|"2026.1 code"| H4["2026.1 DBs<br/>MariaDB 11.4"]
    end
    H4 --> S["2026.1 services<br/>fresh RabbitMQ 4"]
    S --> F["Every old resource<br/>read back and operated<br/>(servers, volumes,<br/>networks, users)"]
    N["❌ 2026.1 code<br/>directly on Ussuri"] -. "refused:<br/>no legacy path" .-> U
    classDef old fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef mid fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef ok fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef no fill:#f3f4f6,stroke:#9ca3af,color:#6b7280,stroke-dasharray: 4 4
    class U old
    class H1,H1b,H2,H3 mid
    class H4,S,F ok
    class N no
```

| Finding | Status |
|---|---|
| A direct jump is impossible: 2026.1 Nova, Keystone and Cinder cannot read a Ussuri database | Confirmed in the lab |
| Database fast-forward Ussuri → 2026.1 with no intermediate deployment, zero unexpected schema or data change | Lab-verified, synthetic data, unsupported upstream |
| 2026.1 services start on the result and operate old servers, volumes, networks and users | Lab-verified, synthetic data |
| A Cinder bug breaks the **official** 2023.1 → 2024.1 upgrade for clouds with old deleted volumes | [Documented](journeys/ussuri-to-2026.1/troubleshooting/cinder-use-quota-null-blocks-2024.1-db-sync.md) |
| Kolla-Ansible 2026.1 changes data when deployed on existing databases; ten mandatory steps identified | Lab-verified for the commands; Kolla itself not run |

Not yet done: rollback rehearsal, a real Kolla-Ansible lab with real VMs, a run on a production copy. Details:
[journey page](journeys/ussuri-to-2026.1/index.md) ·
[final report](journeys/ussuri-to-2026.1/reports/2026-10-31-final-report-session-1.md) ·
[draft runbook](journeys/ussuri-to-2026.1/runbooks/ussuri-to-2026.1-database-fast-forward-lab-runbook.md).

> [!WARNING]
> **Nothing here is a supported or production-validated procedure.** Never run a step on a platform whose data you
> cannot afford to lose without your own backups, your own rehearsal and your own change review.

## 🏷️ How claims are labelled

Every step and every result carries one of these statuses. Reading code or documentation never counts as validation.

```mermaid
flowchart LR
    P["🧪 PROPOSED-UNVERIFIED<br/><i>an idea, nobody ran it</i>"] --> L
    D["📄 DOCUMENTED-UNVERIFIED<br/><i>from docs or code</i>"] --> L
    L["🟩 LAB-VALIDATED<br/><i>ran on a lab, evidence kept</i>"] --> PR["🟦 PRODUCTION-VALIDATED<br/><i>a human operator confirmed it</i>"]
    L -. "something changed" .-> N["🔁 NEEDS-REVALIDATION"]
    L -. "did not work" .-> F["🟥 FAILED<br/><i>kept as a warning</i>"]
    classDef grey fill:#f3f4f6,stroke:#9ca3af,color:#111827
    classDef green fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blue fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef amber fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef red fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class P,D grey
    class L green
    class PR blue
    class N amber
    class F red
```

Claims about what is *possible* use a second vocabulary: officially supported, technically possible but unsupported,
experimentally validated, not validated, incompatible. Rules and mapping to the other OzarLand repositories:
[`docs/validation-status.md`](docs/validation-status.md).

## 🗺️ Journeys

| Journey | Question | Stage |
|---|---|---|
| [Ussuri → 2026.1](journeys/ussuri-to-2026.1/index.md) | Can a Kolla-Ansible Ussuri cloud reach 2026.1 in one journey, and what is the safest path with the fewest intermediate deployments? | Lab experiments; draft runbook; nothing production-validated |

Another starting release or deployment method? Propose it in an
[*Ideas* discussion](https://github.com/OzarLand/ozarland/discussions/new?category=ideas).

## 🗂️ Inside a journey

```mermaid
flowchart TD
    J["journeys/&lt;from&gt;-to-&lt;to&gt;/"] --> A["assessments/<br/>one report per specialist"]
    J --> DR["decision-records/<br/>DR-NNN, with dissent"]
    J --> EX["experiments/<br/>EXP-NNN: hypothesis,<br/>steps, conclusion"]
    EX --> EV["evidence/<br/>redacted outputs"]
    EX --> VA["validation/<br/>VAL-NNN.yaml"]
    VA --> RB["runbooks/<br/>only from validated steps"]
    J --> TS["troubleshooting/<br/>symptoms met on the way"]
    J --> RP["reports/<br/>progress and final"]
    classDef neutral fill:#f3f4f6,stroke:#9ca3af,color:#111827
    classDef go fill:#dcfce7,stroke:#16a34a,color:#14532d
    class J,A,DR,EX,EV,VA,TS,RP neutral
    class RB go
```

Laboratory scripts live in [`lab/`](https://github.com/OzarLand/ozarland-academy/tree/main/docs/upgrade/lab), templates in [`docs/templates/`](https://github.com/OzarLand/ozarland-academy/tree/main/docs/upgrade/docs/templates).

## 🤝 Contributing

The most valuable contribution is **evidence**: you ran a step on a lab or a real platform and it worked, failed or
worked partly. Then: a wrong or unsafe step, or your own starting point for a next journey.

- [Report a run](https://github.com/OzarLand/ozarland-academy/issues/new?template=upgrade-experiment-report.yml) ·
  [Report a wrong or unsafe procedure](https://github.com/OzarLand/ozarland-academy/issues/new?template=upgrade-unsafe-or-wrong-procedure.yml) ·
  [CONTRIBUTING.md](CONTRIBUTING.md)
- Never publish credentials, real hostnames, database dumps or unredacted logs
  ([sensitive data](https://github.com/OzarLand/ozarland/blob/main/docs/conventions/sensitive-data.md)).

> [!NOTE]
> The investigation is carried out by a team of AI agents with separate roles (architect, compatibility,
> Kolla-Ansible, databases, laboratory, operations, documentation, and an independent red team), working from the
> upstream sources and the [OzarLand operator skills](https://github.com/OzarLand/openstack-operator-skills), under
> the direction of the OzarLand owner. No human operator has confirmed a result on a real platform yet; that is the
> contribution we are looking for.

## 🌍 Part of OzarLand Academy

This module is a stop of [OzarLand Academy](../), the learning path of
[OzarLand](https://github.com/OzarLand/ozarland): *a shared land for better OpenStack operations.* It builds on the
[day-2 operations with Kolla-Ansible](../day2/), whose Ussuri study describes the starting point of the first
journey, and on the [Production guide](../production/).

## ⚖️ License

[Apache-2.0](https://github.com/OzarLand/ozarland-academy/blob/main/LICENSE). OzarLand is not affiliated with the OpenStack Foundation, the OpenInfra Foundation or any
vendor; OpenStack and Kolla-Ansible are the work of their upstream communities.

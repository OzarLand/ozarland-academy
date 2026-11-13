# Publication readiness report

Review performed on 2026-11-12 on the working branch; scans of the tree and
of the history of `main` repeated on 2026-11-13 after the knowledge base,
the contribution workspace and the documentation review were merged. The repository is **private**; this report lists what was
checked before a possible public release and what remains for the
maintainers to decide. Nothing in it changes the repository visibility.

## Summary

| Area | Result |
|---|---|
| Secrets and credentials in the tree | None found |
| Secrets and credentials in Git history | None found |
| Infrastructure-specific information | None found |
| IP addresses | Private (RFC 1918), loopback and documentation ranges only, plus two public DNS resolvers used as defaults |
| Scripts and configuration | Lint-clean; executed end to end on one environment |
| Documentation consistency | Links valid; every scenario page carries a validation status |
| License and third-party content | Apache-2.0; derived files attributed |
| Git history | Eleven commits on `main` (one per merged pull request), Conventional Commits style |
| Contribution guidelines | Present |
| Examples generic and reproducible | Yes, with the limits listed below |

**Assessment: ready for publication once the open points in the last
section are decided.** None of them is a blocker for confidentiality.

## 1. Secrets and credentials

- Pattern scan of the working tree and of the full history (`git log -p`)
  for passwords, tokens, API keys, private key headers and cloud access key
  formats: no match other than Kubernetes field names
  (`ansibleSSHPrivateKeySecret`).
- Design review: cloud credentials are read from the operator's own
  OpenStack client configuration and never copied; service passwords are
  generated inside the cluster; `lab.env`, `*.tfvars`, `.work/`, key files,
  kubeconfig and `clouds.yaml` are ignored by Git; the copy to the bastion
  sends tracked files only.
- The only key material in the repository is an obviously fake public key
  used as a test fixture.

Recommendation: enable GitHub secret scanning and push protection when the
repository becomes public.

## 2. Infrastructure-specific information

Searched for the names of the cloud provider, its region and availability
zone, the workstation host name, project and user names, resource
identifiers and the proxy product used during validation: no occurrence in
the tree or in commit messages. Environment quirks met during validation are
expressed as optional, neutrally named settings (`HTTP_PROXY_URL`,
`BASTION_NTP_SERVER`, `ISO_BLANK_SYSTEM_AREA`, `floating_ip_subnet_id`).

## 3. IP addresses and network details

Every literal address in the tree belongs to: the lab defaults
(`192.168.130.0/24`, `192.168.122.0/24`, `172.17.0.0/24`, `172.19.0.0/24`),
cluster-internal defaults (`10.128.0.0/14`, `172.30.0.0/16`), loopback, the
documentation ranges of RFC 5737, or the public resolvers `1.1.1.1` and
`9.9.9.9` used as default DNS forwarders. No floating IP or address of the
validation environment appears.

## 4. Scripts and configuration files

| Check | Result |
|---|---|
| ShellCheck (`-x`) on all scripts | 0 findings with releases 0.9 and 0.11 |
| ruff check and format on the Python helper | clean |
| yamllint on static YAML | clean |
| Offline rendering of the 11 manifest templates | all valid |
| `terraform fmt` | clean; `validate` and `apply` run on the validation environment |
| markdownlint on all Markdown files | 0 issues |

An independent code review was performed before the first deployment
(28 findings: 4 blocking, the rest hardening and clarity). All were applied
or explicitly rejected with a reason during deployment; two are applied but
were not exercised by a failing case (necessity of the libvirt secret,
detection of a terminally failed data plane deployment).

The GitHub Actions workflow (`.github/workflows/lint.yml`) runs on pull
requests and on pushes to `main`. Its first runs exposed two problems that
local checks could not: the workflow did not start until third-party actions
were replaced by plain commands, and the runner's older ShellCheck release
reports indirectly invoked functions under a different code. Both are fixed
and the three jobs pass.

## 5. Documentation consistency and completeness

- All relative links resolve.
- 29 scenario pages: 12 validated on the lab, 17 partially validated; each
  partial page states what was not executed and why (destructive steps,
  restores, upgrades without an available target).
- `docs/versions.md` is the single source for versions, validation status
  and known limitations, and matches the README.
- Not executed anywhere, and documented as such: a volume-snapshot
  rollback, an operator upgrade through OLM, the OKD upgrade, the QEMU
  emulation path, the layout without floating IPs. The restores of the
  databases and of etcd, and the additional compute nodes, were exercised
  after the first review; `docs/versions.md` holds the current status.

## 6. License and third-party content

- The repository is under the Apache License 2.0.
- Manifests derived from `openstack-k8s-operators/openstack-operator`
  samples and from `install_yamls` (both Apache-2.0) carry a comment naming
  their source; the README has an acknowledgements section.
- No third-party binary, image or copied documentation is stored. Upstream
  artefacts (OKD installer, cert-manager, MetalLB, CRDs) are downloaded at
  run time from pinned versions.
- `deployment/infrastructure/.terraform.lock.hcl` is committed on purpose
  (provider version pinning).

## 7. Git history

- Conventional Commits style, no reference to tooling used to
  produce them.
- `main` holds the initial commit and one squashed commit for the first
  version, both under a personal `noreply` address.
- No large file, no generated artefact, no file later removed for
  confidentiality reasons.

## 8. Repository structure and contribution guidelines

`README.md` (purpose, architecture, prerequisites, deployment, documentation
index, learning roadmap, tested versions, limitations), `CONTRIBUTING.md`
(ground rules, lint, conventions), `LICENSE`, `Makefile` (lint targets), CI
workflow. Missing, optional for a first release: issue and pull request
templates, a code of conduct, a security policy.

## 9. Examples generic and reproducible

- `config/lab.env.example` and `terraform.tfvars.example` contain
  placeholders and neutral defaults only.
- Reproducibility limits to state honestly at publication:
  - validated on a single host cloud, behind an HTTP proxy, with floating
    IPs and nested KVM;
  - the operator catalog is pinned to the validated digest, but the package
    repositories of the compute nodes follow a moving tag;
  - OKD 4.22 no longer receives builds and currently has no upgrade edge.

## Open points for the maintainers

1. **Commit identity.** The first version was merged into `main` as a single
   squashed commit, attributed by the hosting platform to the account that
   opened the pull request (a personal `noreply` address), like the initial
   commit. Confirm this is the identity wanted in public history; rewriting
   it later would change the commit hashes.
2. **Working branches.** The branches used to prepare the merged pull
   requests still exist on the remote (the first working branch, the
   `ops-kb*` branches and `contrib-prep`); everything they hold is in
   `main`. Delete them before publication.
3. **Catalog refresh.** The example settings pin the validated catalog
   digest; decide how often to re-validate against a newer catalog.
4. **Community files.** Add issue/PR templates, a code of conduct and a
   security policy if outside contributions are expected.
5. **Second environment.** A run on another host cloud (direct Internet
   access, no proxy) would validate the default path, which has only been
   exercised through its optional settings.

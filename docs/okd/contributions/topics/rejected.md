# Findings examined and not kept

Each finding below looked like a contribution subject and was dropped
after checking upstream. They are kept here so that nobody spends the
same hour twice. All checks were made on 2026-11-13 unless a date is
given.

| Finding | Where it came from | Why it was not kept | Pointer |
| --- | --- | --- | --- |
| IPv6 `memcached_servers` rendered without the `inet6:` prefix | open upstream issue | The reporter opened the fix the same day; the pull request is still open. Taking it over would be discourteous; testing it is possible but it is not a lab subject (the lab is IPv4 only). | `openstack-k8s-operators/nova-operator` issue #1216 and pull request #1217 (2026-09-23) |
| SOS reports empty in must-gather (hard link across devices) | open upstream issue | A fix by the reporter is open since March 2026. Reading the script shows `gather_sos` already tolerates the failure (L130) while `gather_edpm_sos` does not (L102). A review comment could help; it is not the owner's subject. | `openstack-k8s-operators/openstack-must-gather` issue #131, pull request #132 |
| Data plane Jobs are never garbage-collected | lab observation (finished Jobs accumulate) | Fixed on `main`: Jobs now get a time-to-live through `reconcileJobTTL`. | `openstack-k8s-operators/openstack-operator` pull request #2159 |
| No way to raise the log level of memcached and dnsmasq | lab wish during troubleshooting | An outside contributor proposed both in September 2026; maintainers answered within two hours and merged their own versions. Useful as a measure of responsiveness, nothing left to do. | `openstack-k8s-operators/infra-operator` pull requests #687, #688 (closed), #693, #689 (merged) |
| `openstack server migrate --live-migration --wait` prints "Complete" for a migration that failed | lab drill | Known and stated limitation: the client prints "Complete, check success/failure by openstack server migration/event list/show". A behaviour change would be a design discussion in an OpenStack project, not a first contribution. | `openstack/python-openstackclient`, `openstackclient/compute/v2/server.py` near L3491-L3506 at `f1f7ff03` (2026-11-10) |
| A new compute node is not usable until host discovery is run by hand | lab scale-out | Documented manual step, by design. | `openstack-operator` `docs/assemblies/dataplane_scaling_out.adoc` L82-L87 at `1a58205d` |
| The machine-config controller waits minutes for its leader lease after a restart | lab reboot drill | Artefact of a single-node cluster that restarts abruptly: the lease is released on clean shutdown (`ReleaseOnCancel: true`). Not a defect. | `openshift/machine-config-operator`, `cmd/machine-config-controller/start.go` L242 |
| `configMapHashes` in the NodeSet status keeps entries of removed ConfigMaps | code reading | Cosmetic status field, no observed consequence on the lab; evidence too weak for a report. Could be mentioned inside topic 03 if that fix is discussed. | `openstack-operator` `internal/controller/dataplane/openstackdataplanenodeset_controller.go` L640-L655 at `1a58205d` |
| "No update path from 4.22.0-okd-scos.10" as an OKD bug | lab upgrade page | Not a bug: the cluster looks at the former update source and channel. It became documentation topic 11. | [topic 11](11-okd-update-service-docs.md) |
| Fixes to the OKD product documentation | reading the docs during the lab build | The repository is in maintenance mode and refuses contributions from outside its team until the documentation migration ends; documentation bugs go to the product tracker, which requires an account. | `openshift/openshift-docs`, `contributing_to_docs/contributing.adoc` L12-L20 at `99763c1d88` (2026-11-12) |
| OVN negative DNS cache of one hour after an outage | lab outage drills | Addressed upstream in October 2026 by a configurable resolver configuration with a 30 second negative cache. What the lab observed lasts much longer and is kept as topic 05; the cache itself is no longer a subject. | `openstack-k8s-operators/edpm-ansible` pull requests #1337 (`main`) and #1338 (`18-stable`) |
| Stale upstream issues without activity (several repositories) | listing of open, unassigned issues in the organisation | Most open issues are dependency dashboards; the few real ones are either feature requests without maintainer opinion or reports too old to verify on current code. The team tracks its work in a product tracker, so the GitHub issue list is not where subjects are found. | organisation-wide issue search, 82 open issues on 2026-11-13 |

## What this list says about method

- Half of the lab's "bugs" were already fixed on `main`. Always read
  `main` before writing a line.
- A report whose author already sent a fix is not available, however
  long it has been waiting. The useful action there is a tested review.
- Behaviour that is documented as manual is a feature request, and a
  feature request from a newcomer needs a maintainer's opinion first.

# Contribution journal

One entry per action taken towards upstream, newest first. The journal is
the memory of the contribution effort: what was sent, where, and what came
back. Nothing has been sent upstream yet: the entries so far are lab
observations and code reading.

## Entry format

```markdown
## YYYY-MM-DD — short title

- **Topic:** [NN-slug](topics/NN-slug.md)
- **Action:** what was done (lab validation run, issue filed, patch sent,
  review answered, question asked on a channel)
- **Link:** URL of the issue, pull request, review or thread; path of the
  evidence when the action was a lab run
- **Outcome:** what came back (confirmed, needs information, rejected with
  the reason, merged with the commit, no answer yet)
- **Next step:** the next action and who is expected to take it
```

Rules:

- Write the entry the same day as the action, including for actions that
  led nowhere: a rejected report is information for the next one.
- A lab run is an action. Record what was run, on which versions, and what
  was observed, before any claim is made upstream.
- When an entry changes the state of a topic, update the status board in
  [README.md](README.md) in the same commit.
- No addresses, host names or credentials of the host environment, here as
  everywhere else in the repository.

## Entries

## 2026-11-14 — OVN agents: recovery without restart timed, code read

- **Topic:** [05-ovn-agents-stuck-after-dns-outage](topics/05-ovn-agents-stuck-after-dns-outage.md)
- **Action:** read-only observation of a start of the whole lab that
  nobody provoked (package `ovn24.03-24.03.8-55.el9s`, Open vSwitch
  library 3.3.8, `unbound-libs` 1.26.1, one nameserver); journals of
  the two previous boots re-read; Open vSwitch, OVN, Unbound and
  edpm-ansible sources read. No outage was provoked and nothing was
  changed on the node.
- **Link:** lab evidence directory `ovn-stuck/`, files 01 to 11
- **Outcome:** the agents reconnect by themselves, 15 and 16 minutes
  after their start; "never reconnect" and "18 hours" withdrawn; the
  shipped Unbound file is in the lab build and does not prevent the
  delay; origin of the error text established in the code; mechanism
  of the delay (libunbound infrastructure cache, 900 s) probable, not
  proven. Topic 06 corrected on the same points.
- **Next step:** a provoked DNS outage with a packet capture, then
  the same with `infra-keep-probing: yes` (plan in the topic); to be
  decided by the lab owner. Nothing to send upstream before that.

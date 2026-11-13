# Pull request preparation checklist

Go through this list for every change sent upstream, and keep the ticked
copy in the topic page. The project-specific commands, branch names and
review rules are in [the methodology](../methodology.md); this page is the
order of operations.

## 1. Before writing anything

- [ ] The topic page exists and its "Upstream state" section was
      re-checked this week: no new issue, pull request or commit makes the
      change redundant.
- [ ] For anything larger than a typo or a one-line fix, an issue exists
      or a maintainer has agreed on the direction. A change nobody asked
      for is a review burden.
- [ ] The problem is reproduced on the lab, and the run is in
      [the journal](../log.md).
- [ ] The target branch is the development branch of the project. Stable
      branches receive backports of merged changes, not original work.
- [ ] The contribution guide of the target repository was read again; it
      may have changed since the methodology was written.

## 2. The change

- [ ] One logical change. A fix and a refactoring are two pull requests.
- [ ] As small as possible: a reviewer should be able to hold it in mind.
- [ ] Follows the style of the surrounding code or documentation; no
      reformatting of untouched lines.
- [ ] A test fails without the change and passes with it, in the test
      framework the repository already uses. If no test is possible, the
      description says why and how the change was verified by hand.
- [ ] Documentation and samples updated when behaviour or an interface
      changes.
- [ ] Generated files regenerated with the project's own targets and
      committed with the change.

## 3. Local verification

- [ ] The linters and unit tests required by the repository pass locally,
      with the tool versions the repository pins.
- [ ] The change was exercised on the lab, or the description states
      precisely what was not exercised.
- [ ] The branch is rebased on the current target branch.

## 4. Commit and description

- [ ] Commit message in the form the project uses: subject line, body that
      explains why, references to the issue or ticket in the expected
      syntax.
- [ ] Sign-off trailer present when the project requires it; the author
      name and e-mail are those of the contributor's own account.
- [ ] The description states: the problem, the fix, how it was tested,
      what was not tested, and the deployment it was observed on.
- [ ] No address, host name, domain or credential of the host environment
      in the diff, the commit message, the description or attached logs.
- [ ] The pull request template of the repository is filled, not deleted.

## 5. After opening

- [ ] Recorded in [the journal](../log.md) and on the status board.
- [ ] Continuous integration results read; failures understood before
      asking for a re-run. A re-run command is not a fix.
- [ ] Review comments answered within a few days, each one either applied
      or discussed; none ignored.
- [ ] Changes after review pushed the way the project prefers (additional
      commits or amended commit) so that the reviewer can see what moved.
- [ ] No reminder before the usual review latency of the repository has
      passed; one polite reminder on the channel the project names, then
      patience.
- [ ] When merged: backport requested only if the project's rules allow it
      and a maintainer agrees; topic page, status board and journal
      updated; the lab documentation updated if the workaround it
      describes is no longer needed.

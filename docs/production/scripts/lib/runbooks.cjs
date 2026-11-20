'use strict';
// Checks every runbook reference against the pages of the module VM runbooks of OzarLand Academy
// (docs/runbooks/, next to this module): the page exists, and its status and release are the ones the memo
// prints. A memo never links to a path that was not seen there.

const fs = require('fs');
const path = require('path');
const { ROOT } = require('./content.cjs');

const REPO = 'https://github.com/OzarLand/ozarland-academy';
// The runbook on GitHub: for plain text that leaves the portal (a LinkedIn caption).
const BLOB = `${REPO}/blob/main/docs/runbooks/`;

// Address of the page of a runbook in the portal, relative to a generated page of this module (`from` is its
// directory under docs/production/, '' for the home page). The modules are separate sites of the portal: a link
// to another one is the address of its page, ending with '/', checked by tools/site/check_docs.py.
function runbookLink(p, from) {
  const page = `runbooks/${p.replace(/\.md$/, '').replace(/(^|\/)index$/, '$1')}`;
  const rel = path.posix.relative(path.posix.join('production', from), page);
  return rel.endsWith('/') ? rel : `${rel}/`;
}

function findCheckout(explicit) {
  const candidates = [explicit, process.env.RUNBOOKS_DIR, path.join(ROOT, '..', 'runbooks')].filter(Boolean);
  for (const c of candidates) if (fs.existsSync(path.join(c, 'index.md')) && fs.existsSync(path.join(c, 'lifecycle'))) return c;
  return null;
}

function frontMatter(file) {
  const t = fs.readFileSync(file, 'utf8');
  const fm = /^---\n([\s\S]*?)\n---/.exec(t);
  const get = (k) => (fm ? (new RegExp(`^${k}:\\s*(.+)$`, 'm').exec(fm[1]) || [])[1] : undefined);
  const title = (/^# (.+)$/m.exec(t) || [])[1];
  return {
    title,
    status: get('status'),
    risk: get('risk'),
    releases: (get('openstack_releases') || '').replace(/[\[\]"' ]/g, '').split(',').filter(Boolean),
  };
}

function checkRunbooks(memos, dir) {
  const errors = [];
  for (const m of memos) {
    const rb = m.runbook || {};
    const all = [rb.path, ...(rb.also || [])].filter(Boolean);
    m._runbooks = [];
    for (const p of all) {
      const file = path.join(dir, p);
      if (!fs.existsSync(file)) {
        errors.push(`${m._file}: runbook "${p}" does not exist in docs/runbooks`);
        continue;
      }
      const fm = frontMatter(file);
      m._runbooks.push({ path: p, url: BLOB + p, ...fm });
      if (p !== rb.path) continue;
      if (fm.status !== rb.status) errors.push(`${m._file}: runbook.status is "${rb.status}" but the runbook says "${fm.status}"`);
      if (!fm.releases.includes(String(rb.release)))
        errors.push(`${m._file}: runbook.release is "${rb.release}" but the runbook lists ${fm.releases.join(', ') || 'none'}`);
    }
  }
  return errors;
}

module.exports = { REPO, BLOB, runbookLink, findCheckout, checkRunbooks };

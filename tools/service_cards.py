#!/usr/bin/env python3
"""Per-service "cards" for the core services: role, play, tags, task flow,
templates, handlers, key variables and which node types are touched.

Usage: service_cards.py [--release <id>] <kolla-ansible checkout> <inventory.json from
`ansible-inventory -i ansible/inventory/multinode --list`> [components directory]

The cards live in the component pages of one release (default directory:
docs/day2/<id>/components, where <id> is the release given with --release, or the
default release of the day-2 module in academy.toml). The checkout must be at the tag of that
release. Each page holds its card(s) between two markers:

    <!-- BEGIN GENERATED: tools/service_cards.py <role> [<role> ...] -->
    <!-- END GENERATED -->

Only the text between the markers is rewritten. A page that lists several roles
gets one "### <title> — role `<role>`" sub-section per role.

Node types are resolved against the example `multinode` inventory of the release
(control / network / compute / storage / monitoring).
"""
import glob, json, os, re, sys
import yaml

def release_argument(argv):
    """Take `--release <id>` (or `--release=<id>`) out of the arguments.

    Returns (docs directory of the release, remaining arguments). Without the
    option the release is the default one of the day-2 module (academy.toml).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, 'site'))
    import releases
    rest, release = [], None
    args = iter(argv)
    for arg in args:
        if arg == '--release':
            release = next(args, None)
            if release is None:
                sys.exit('--release needs the id of a release')
        elif arg.startswith('--release='):
            release = arg.split('=', 1)[1]
        else:
            rest.append(arg)
    root = os.path.dirname(here)
    try:
        registry = releases.load_registry(releases.Path(root))
        release = releases.select(registry, release or registry.default)[0]
    except releases.RegistryError as error:
        sys.exit('academy.toml: ' + '; '.join(error.problems))
    return os.path.join(root, *release.docs_dir.split('/')), rest


DOCS, ARGS = release_argument(sys.argv[1:])
SRC, INV = ARGS[0:2]
PAGES = ARGS[2] if len(ARGS) > 2 else os.path.join(DOCS, 'components')
A = os.path.join(SRC, 'ansible')
inv = json.load(open(INV))


def hosts_of(group, seen=None):
    seen = seen or set()
    if group in seen or group not in inv:
        return set()
    seen.add(group)
    g = inv[group]
    hs = set(g.get('hosts', []))
    for c in g.get('children', []):
        hs |= hosts_of(c, seen)
    return hs


def kinds(hosts):
    k = set()
    for h in hosts:
        m = re.match(r'([a-z]+)', h)
        if m:
            k.add({'control': 'control', 'network': 'network', 'compute': 'compute',
                   'storage': 'storage', 'monitoring': 'monitoring'}.get(m.group(1), m.group(1)))
    return ', '.join(sorted(k)) or '–'


site = open(os.path.join(A, 'site.yml')).read().splitlines()
site_plays = yaml.safe_load(open(os.path.join(A, 'site.yml')))


def plays_of(role):
    """(play, role entry) for every site.yml play that applies `role` through `roles:`."""
    res = []
    for p in site_plays:
        for r in p.get('roles') or []:
            name = r.get('role') if isinstance(r, dict) else r
            if name == role:
                res.append((p, r if isinstance(r, dict) else {}))
    return res


def as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])


def play_line(role):
    for i, l in enumerate(site, 1):
        if l.strip() == '- name: Apply role %s' % role:
            return i
    return None


CORE = [
    ('MariaDB/Galera', 'mariadb', ['enable_mariadb', 'mariadb_*', 'database_address', 'enable_external_mariadb_load_balancer']),
    ('RabbitMQ', 'rabbitmq', ['enable_rabbitmq', 'om_rpc_*', 'rabbitmq_*', 'rpc_transport_url']),
    ('Memcached', 'memcached', ['enable_memcached', 'memcached_port']),
    ('HAProxy + Keepalived', 'haproxy', ['enable_haproxy', 'enable_keepalived', 'kolla_internal_vip_address', 'kolla_external_vip_address', 'keepalived_virtual_router_id', 'kolla_enable_tls_*']),
    ('Fluentd / cron / kolla-toolbox', 'common', ['enable_fluentd', 'enable_* (all, via td-agent/logrotate)', 'elasticsearch_address', 'enable_monasca']),
    ('Open vSwitch', 'openvswitch', ['enable_openvswitch', 'neutron_bridge_name', 'neutron_external_interface', 'computes_need_external_bridge']),
    ('OVN', 'ovn', ['enable_ovn', 'neutron_plugin_agent: ovn', 'neutron_ovn_distributed_fip']),
    ('Chrony', 'chrony', ['enable_chrony', 'external_ntp_servers']),
    ('iscsid / tgtd', 'iscsi', ['enable_iscsid', 'enable_cinder_backend_lvm']),
    ('Keystone', 'keystone', ['enable_keystone', 'keystone_token_provider', 'fernet_token_expiry', 'fernet_key_rotation_interval']),
    ('Glance', 'glance', ['enable_glance', 'glance_backend_*', 'glance_api_hosts', 'glance_enable_rolling_upgrade']),
    ('Placement', 'placement', ['enable_placement']),
    ('Nova (API level)', 'nova', ['enable_nova', 'enable_cells', 'nova_safety_upgrade', 'nova_console']),
    ('Nova (cell level)', 'nova-cell', ['nova_compute_virt_type', 'nova_backend_ceph', 'libvirt_tls', 'libvirt_enable_sasl', 'nova_cell_*_group', 'migration_interface']),
    ('Neutron', 'neutron', ['enable_neutron', 'neutron_plugin_agent', 'enable_neutron_dvr', 'enable_neutron_agent_ha', 'enable_neutron_provider_networks', 'neutron_enable_rolling_upgrade']),
    ('Cinder', 'cinder', ['enable_cinder', 'enable_cinder_backend_*', 'cinder_backend_ceph', 'cinder_backup_driver', 'cinder_coordination_backend']),
    ('Horizon', 'horizon', ['enable_horizon', 'enable_horizon_*', 'horizon_backend_database']),
    ('Heat', 'heat', ['enable_heat', 'heat_*_external_fqdn']),
    ('Barbican', 'barbican', ['enable_barbican', 'barbican_crypto_key (passwords.yml)']),
    ('Octavia', 'octavia', ['enable_octavia', 'octavia_amp_*', 'octavia_network_interface']),
    ('Swift', 'swift', ['enable_swift', 'swift_devices_*', 'swift_*_server ports']),
    ('Manila', 'manila', ['enable_manila', 'enable_manila_backend_*']),
]

# Card rows: "Node types in play" = every host matched by the play's host patterns (before `enable_*` filtering);
# "Node types running its containers" = hosts where at least one container of the role is placed (group-based
# placement; `host_in_groups` expressions are summarised by their groups).
# Roles renamed or split in later releases; a role absent from the checkout gets
# no card (its page then has no marker).
RENAMED = {'haproxy': [('HAProxy + Keepalived', 'loadbalancer')],
           'ovn': [('OVN controller', 'ovn-controller'), ('OVN databases', 'ovn-db')]}
core = []
for title, role, keyvars in CORE:
    if os.path.isdir(os.path.join(A, 'roles', role)):
        core.append((title, role, keyvars))
    else:
        core += [(t, r, keyvars) for t, r in RENAMED.get(role, [])
                 if os.path.isdir(os.path.join(A, 'roles', r))]
nova_line = next((i for i, l in enumerate(site, 1) if re.match(r'\s*-?\s*import_playbook:\s*nova\.yml', l)), '?')
lb_includes = sum(1 for l in site if re.match(r'\s*tasks_from:\s*loadbalancer\s*$', l))
common_deps = sum(1 for m in glob.glob(os.path.join(A, 'roles', '*', 'meta', 'main.yml'))
                  if re.search(r'role:\s*common\b', open(m).read()))
cards = {}
for title, role, keyvars in core:
    rd = os.path.join(A, 'roles', role)
    d = yaml.safe_load(open(os.path.join(rd, 'defaults', 'main.yml'))) or {}
    sv = {}
    for k, v in d.items():
        if k.endswith('_services') and isinstance(v, dict):
            sv.update({sk: s for sk, s in v.items() if isinstance(s, dict) and 'container_name' in s})
    rplays = plays_of(role)
    cnames = []
    chosts = set()
    for s in sv.values():
        # Resolve the role parameters a play passes (e.g. rabbitmq: project_name, role_rabbitmq_groups).
        variants = [rv for _, rv in rplays] or [{}]
        for rv in variants:
            env = {'project_name': rv.get('project_name', d.get('project_name', role))}
            env.update({k: v for k, v in rv.items() if isinstance(v, str)})
            cn = re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: str(env.get(m.group(1), m.group(0))), str(s['container_name']))
            if cn not in cnames:
                cnames.append(cn)
            g0 = re.sub(r'\{\{\s*(role_\w+)\s*\}\}', lambda m: str(env.get(m.group(1), m.group(0))), str(s.get('group') or ''))
            if g0 and g0 != str(s.get('group')):
                chosts |= hosts_of(g0)
    for s in sv.values():
        expr = str(s.get('host_in_groups') or '')
        gs = re.findall(r"groups\[['\"]([A-Za-z0-9_\-]+)['\"]\]", expr) if expr else []
        if not gs and s.get('group'):
            g = str(s['group'])
            g = {'{{ nova_cell_compute_group }}': 'compute', '{{ nova_cell_conductor_group }}': 'nova-conductor',
                 '{{ nova_cell_novncproxy_group }}': 'nova-novncproxy', '{{ nova_cell_spicehtml5proxy_group }}': 'nova-spicehtml5proxy',
                 '{{ nova_cell_serialproxy_group }}': 'nova-serialproxy', '{{ nova_cell_compute_ironic_group }}': 'nova-compute-ironic'}.get(g, g)
            gs = ['all'] if g == 'all' else [g]
        for g in gs:
            chosts |= hosts_of(g)
    if not sv:
        # Old-style roles (swift) start containers with explicit container
        # module tasks: kolla_docker up to 2023.1, kolla_container from 2024.1.
        for tf in sorted(glob.glob(os.path.join(rd, 'tasks', '*.yml'))):
            for t in yaml.safe_load(open(tf)) or []:
                kd = (t.get('kolla_docker') or t.get('kolla_container')) if isinstance(t, dict) else None
                if not kd or kd.get('action') != 'start_container' or '{{' in str(kd.get('name')):
                    continue
                if kd['name'] not in cnames:
                    cnames.append(kd['name'])
                for g in re.findall(r"groups\[['\"]([A-Za-z0-9_\-]+)['\"]\]", str(t.get('when', ''))):
                    chosts |= hosts_of(g)
    pl = play_line(role)
    phosts = set()
    if role in ('nova', 'nova-cell'):
        pl_txt = 'nova.yml (`import_playbook` at site.yml:%s)' % nova_line
        pats = ['nova-api', 'nova-scheduler', 'nova-super-conductor'] if role == 'nova' else ['compute', 'nova-compute-ironic', 'nova-conductor', 'nova-novncproxy', 'nova-serialproxy', 'nova-spicehtml5proxy']
        tags = 'nova, nova-api(-*)' if role == 'nova' else 'nova, nova-cell(-*)'
    elif role == 'common' and common_deps:
        ndeps = common_deps
        pl_txt = ('meta dependency of %d roles (not `memcached`, `multipathd` or the helper roles); runs in the first '
                  'play that reaches each host' % ndeps)
        pats = ['first play reaching each host (chrony by default)']
        tags = 'inherits the tag of the first play reaching the host (`-t common` alone is a no-op)'
        phosts = {h for h in hosts_of('all') if h != 'localhost'}
        chosts = set(phosts)
    elif not rplays and os.path.isfile(os.path.join(A, role + '.yml')):
        # Later releases move some services into a playbook of their own,
        # imported by site.yml (mariadb.yml, rabbitmq.yml).
        line = next((i for i, l in enumerate(site, 1)
                     if re.match(r'\s*-?\s*import_playbook:\s*%s\.yml\s*$' % re.escape(role), l)), '?')
        own = yaml.safe_load(open(os.path.join(A, role + '.yml'))) or []
        pl_txt = '%s.yml (`import_playbook` at site.yml:%s; %d plays)' % (role, line, len(own))
        pats, tagl = [], []
        for p in own:
            for h in as_list(p.get('hosts')):
                if not str(h).startswith('&') and h not in pats:
                    pats.append(h)
            for t in as_list(p.get('tags')):
                if t not in tagl:
                    tagl.append(t)
        tags = ', '.join(tagl)
    else:
        pl_txt = ', '.join('site.yml:%d' % i for i, l in enumerate(site, 1)
                           if l.strip() in ['- name: %s' % p['name'] for p, _ in rplays]) or '?'
        pats, tagl = [], []
        for p, rv in rplays:
            for h in as_list(p.get('hosts')):
                if not str(h).startswith('&') and h not in pats:
                    pats.append(h)
            for t in as_list(p.get('tags')) + as_list(rv.get('tags')):
                if t not in tagl:
                    tagl.append(t)
        tags = ', '.join(tagl)
        if role in ('haproxy', 'loadbalancer'):
            tags += ('; each of the %d per-service `include_role … tasks_from: loadbalancer` tasks in this play also '
                     'carries its service tag' % lb_includes)
    for p in pats:
        phosts |= hosts_of(p)
    tfiles = sorted(os.path.basename(f) for f in glob.glob(os.path.join(rd, 'tasks', '*.yml')))
    steps = []
    dpath = os.path.join(rd, 'tasks', 'deploy.yml')
    for t in (yaml.safe_load(open(dpath)) or []) if os.path.exists(dpath) else []:
        if not isinstance(t, dict):
            continue
        cond = ' (if)' if 'when' in t else ''
        for k in ('import_tasks', 'include_tasks'):
            if k in t:
                steps.append(str(t[k]).replace('.yml', '').strip('"') + cond)
        for k in ('import_role', 'include_role'):
            if k in t:
                steps.append('role:' + str(t[k].get('name') or t[k].get('role')) + cond)
        if t.get('meta') == 'flush_handlers':
            steps.append('flush handlers')
        if 'name' in t and not any(k in t for k in ('import_tasks', 'include_tasks', 'import_role', 'include_role', 'meta')):
            steps.append('task: ' + t['name'] + cond)
    flow = ' → '.join(steps)
    tpls = sorted(os.path.relpath(f, os.path.join(rd, 'templates')) for f in glob.glob(os.path.join(rd, 'templates', '**', '*.j2'), recursive=True))
    hfile = os.path.join(rd, 'handlers', 'main.yml')
    hn = [h.get('name') for h in (yaml.safe_load(open(hfile)) or [])] if os.path.exists(hfile) else []
    cards[role] = (title, [
            '| Item | Value |', '|---|---|',
            '| Play | %s |' % pl_txt,
            '| Tags | %s |' % (tags or '–'),
            '| Play host patterns | %s |' % (', '.join(pats) or '–'),
            '| Node types in play (example inventory) | %s |' % kinds(phosts),
            '| Node types running its containers | %s |' % kinds(chosts),
            '| Containers | %s |' % (', '.join('`%s`' % c for c in cnames) or '–'),
            '| deploy/reconfigure flow (`tasks/deploy.yml`) | %s |' % (flow or '–'),
            '| Task files | %s |' % ', '.join(tfiles),
            '| Templates | %s |' % (', '.join('`%s`' % t for t in tpls[:25]) + (' … (+%d)' % (len(tpls) - 25) if len(tpls) > 25 else '')),
            '| Handlers (definition order) | %s |' % ('; '.join(map(str, hn)) or '–'),
            '| Key variables | %s |' % ', '.join('`%s`' % v for v in keyvars),
            '| Role dependencies | %s |' % ('`common` (meta)' if os.path.exists(os.path.join(rd, 'meta', 'main.yml'))
                                           and re.search(r'role:\s*common\b', open(os.path.join(rd, 'meta', 'main.yml')).read())
                                           else 'none')])

BEGIN = re.compile(r'^<!-- BEGIN GENERATED: tools/service_cards\.py (.+?) -->$')
END = '<!-- END GENERATED -->'
done, pages = [], 0
for path in sorted(glob.glob(os.path.join(PAGES, '*.md'))):
    lines = open(path, encoding='utf-8').read().split('\n')
    out, i, changed = [], 0, False
    while i < len(lines):
        m = BEGIN.match(lines[i])
        out.append(lines[i])
        i += 1
        if not m:
            continue
        roles = m.group(1).split()
        end = lines.index(END, i)
        block = ['']
        for role in roles:
            if role not in cards:
                sys.exit('%s: no card is defined for role %r' % (path, role))
            title, table = cards[role]
            if len(roles) > 1:
                block += ['### %s — role `%s`' % (title, role), '']
            block += table + ['']
            done.append(role)
        changed = changed or block != lines[i:end]
        out += block
        i = end
    if any(BEGIN.match(l) for l in lines):
        pages += 1
        if changed:
            open(path, 'w', encoding='utf-8').write('\n'.join(out))
        print('%s %s' % ('updated  ' if changed else 'unchanged', path))
missing = [r for r in cards if r not in done]
if missing:
    sys.exit('no page has a marker for: ' + ', '.join(missing))
print('%d cards in %d pages' % (len(done), pages))

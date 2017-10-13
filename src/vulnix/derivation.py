import re

from vulnix.utils import call

R_VERSION = re.compile(r'^(\S+)-([0-9]\S*)$')


def pkgname(fullname, version=None):
    """Guesses package name from a derivation name (strips version)."""
    if fullname.endswith('.drv'):
        fullname = fullname[0:fullname.rindex('.drv')]
    if version:
        return fullname.replace('-' + version, '')
    # see builtins.parseDrvName
    m = R_VERSION.match(fullname)
    if m:
        return m.group(1)
    # no idea
    return fullname


def load(path):
    with open(path) as f:
        d_obj = eval(f.read(), {'__builtins__': {}, 'Derive': Derive}, {})
    d_obj.store_path = path
    return d_obj


class Derive(object):

    store_path = None

    # This __init__ is compatible with the structure in the derivation file.
    # The derivation files are just accidentally Python-syntax, but hey!
    def __init__(self, _output=None, _inputDrvs=None, _inputSrcs=None,
                 _system=None, _builder=None, _args=None,
                 envVars={}, derivations=None):
        self.envVars = dict(envVars)
        self.name = self.envVars['name']
        self.version = self.envVars.get('version')
        self.simple_name = pkgname(self.name, self.version)

        self.affected_by = set()
        self.status = None

    @property
    def is_affected(self):
        return bool(self.affected_by)

    @property
    def product_candidates(self):
        variation = self.simple_name.split('-')
        while variation:
            yield '-'.join(variation)
            variation.pop()

    def check(self, nvd, whitelist):
        for candidate in self.product_candidates:
            for vuln in nvd.by_product_name(candidate):
                for affected_product in vuln.affected_products:
                    if not self.matches(vuln.cve_id, affected_product):
                        continue
                    if (vuln, affected_product, self) in whitelist:
                        continue

                    self.affected_by.add(vuln.cve_id)
                    break

    def matches(self, cve_id, cpe):
        # Step 1: determine product name
        prefix = cpe.product + '-'
        if self.name == cpe.product:
            version = None
        elif self.name.startswith(prefix):
            version = self.name.replace(prefix, '', 1)
            if version not in cpe.versions:
                return False
        else:
            # This product doesn't match at all.
            return False

        # We matched the product and think the version is affected.
        return True

    def roots(self):
        return call(
            ['nix-store', '--query', '--roots', self.store_path]).split('\n')

    def referrers(self):
        return call(['nix-store', '--query', '--referrers',
                     self.store_path]).split('\n')
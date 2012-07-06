from opbeat_python.conf import defaults
from pip.vcs import vcs
from pip.util import get_installed_distributions
from pip.vcs import git, mercurial
import sys
import pkg_resources
import os

VCS_NAME_MAP = {
	'git':'git',
	'hg':'mercurial',
	'svn':'subversion'
}

def send_deployment_info(client):
	versions = get_versions_from_installed(client.include_paths)

	versions = dict([(module, {'module':module, 'version':version}) for module, version in versions.items()])

	dist_versions = get_version_from_distributions(get_installed_distributions())
	versions.update(dist_versions)

	rep_info = get_repository_info()

	if rep_info:
		versions['_repository'] = {'module':'_repository', 'vcs':rep_info}

	# Versions are returned as a dict of "module":"version"
	# We convert i here. Just ditch the keys.
	list_versions = [v for k,v in versions.items()]

	server_name = client.name

	data = {'server_name':server_name, 'releases':list_versions}

	urls = [server+defaults.DEPLOYMENT_API_PATH for server in client.servers]
	
	client.build_msg(data=data)

	client.send(servers=urls,**data)

_VERSION_CACHE ={}
def get_versions_from_installed(module_list=None):
	if not module_list:
		return {}

	ext_module_list = set()
	for m in module_list:
		parts = m.split('.')
		ext_module_list.update('.'.join(parts[:idx]) for idx in xrange(1, len(parts) + 1))

	versions = {}
	for module_name in ext_module_list:
		if module_name not in _VERSION_CACHE:
			try:
				__import__(module_name)
			except ImportError:
				continue
			app = sys.modules[module_name]
			if hasattr(app, 'get_version'):
				get_version = app.get_version
				if callable(get_version):
					version = get_version()
				else:
					version = get_version
			elif hasattr(app, 'VERSION'):
				version = app.VERSION
			elif hasattr(app, '__version__'):
				version = app.__version__
			elif pkg_resources:
				# pull version from pkg_resources if distro exists
				try:
					version = pkg_resources.get_distribution(module_name).version
				except pkg_resources.DistributionNotFound:
					version = None
			else:
				version = None

			if isinstance(version, (list, tuple)):
				version = '.'.join(str(o) for o in version)
			_VERSION_CACHE[module_name] = version
		else:
			version = _VERSION_CACHE[module_name]
		if version is None:
			continue
		versions[module_name] = version

	return versions

def get_version_from_distributions(distributions):
	result = {}
	for d in distributions:
		
		result[d.key] = {'module':d.key}

		if d.has_version():
			result[d.key]['version'] = d.version

		vcs_version = get_version_from_location(d.location)
		if vcs_version:
			result[d.key]['vcs'] = vcs_version

	return result

# Recursively try to find vcs.
def get_version_from_location(location):
	backend_cls = vcs.get_backend_from_location(location)
	if backend_cls:
		backend = backend_cls()
		url, rev = backend.get_info(location)

		vcs_type = VCS_NAME_MAP[backend_cls.name]

		return {'type': vcs_type,'revision':rev, 'repository':url}
	else:
		head, tail = os.path.split(location)
		if head and head != '/': ## TODO: Support windows
			return get_version_from_location(head)
		else:
			return None

def get_repository_info():
	import os
	location = os.getcwd()
	cwd_rev_info = get_version_from_location(location)
	return cwd_rev_info
	
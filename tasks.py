#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Deploys nbviewer on docker

Two pieces:

First set of commands help setup nbviewer servers on Rackspace:

    servers, new_machine, doitall

Second set are for deploying nbviewer with docker on a single node
(assumes docker env is already setup):

    build, pull, nbviewer, upgrade, bootstrap, etc.
"""

from __future__ import print_function

from functools import lru_cache
import json
import os
import pipes
import re
import socket
import sys
import time
join = os.path.join

from invoke import run, task
from docker import APIClient as Client
from docker.utils import kwargs_from_env
from machine import Machine
import requests


NBVIEWER = 'jupyter/nbviewer'
NBCACHE = 'jupyter/nbcache'
LOGENTRIES = 'logentries/docker-logentries'
NODE_FLAVOR = 'general1-2'
HERE = os.path.dirname(os.path.abspath(__file__))
MACHINE_DIR = 'machine'
os.environ['MACHINE_STORAGE_PATH'] = MACHINE_DIR

SERVER_NAME_PAT = re.compile(r'nbviewer\-(\d+)')

creds = {}
with open('creds') as f:
    exec(f.read(), creds)

#------- Local commands for managing rackspace servers --------

@lru_cache()
def rackspace_client():
    from rackspace.connection import Connection

    return Connection(
        username=creds['OS_USERNAME'],
        api_key=creds['OS_PASSWORD'],
        region='DFW',
    )

@lru_cache()
def nbviewer_servers():
    c = rackspace_client()
    return list(c.compute.servers(name='nbviewer'))

@task
def trigger_build(ctx):
    url_base = "https://registry.hub.docker.com/u/jupyter/nbviewer/trigger/{}/" 
    requests.post(url=url_base.format(creds['DOCKER_TRIGGER_TOKEN']), data="build=true")

@task
def new_machine(ctx):
    """Allocate a new server with docker-machine"""
    existing_server_ids = [
        int(SERVER_NAME_PAT.match(s.name).group(1))
        for s in nbviewer_servers()
    ]
    server_id = max(existing_server_ids) + 1
    name = 'nbviewer-%s' % server_id
    env = {}
    env['OS_USERNAME'] = creds['OS_USERNAME']
    env['OS_API_KEY'] = creds['OS_PASSWORD']
    env['OS_FLAVOR_ID'] = NODE_FLAVOR
    
    rc = rackspace_client()
    images = [ image for image in rc.compute.images() if 'Ubuntu 16.04' in image.name]
    image = [ image for image in images if 'PVHVM' in image.name][0]
    env['OS_IMAGE_ID'] = image.id
    env['OS_REGION_NAME'] = "DFW"
    ctx.run('docker-machine create %s --driver=rackspace' % name, env=env, echo=True)
    return name

@task
def add_node(ctx):
    """Add a node to the cluster"""
    name = new_machine(ctx)
    ctx.run("""
        eval $(docker-machine env %s)
        invoke bootstrap
    """ % name, echo=True)
    # add it to fastly
    fastly(ctx)

@task
def remove_node(ctx, name):
    """Remove a docker machine"""
    ctx.run('docker-machine rm %s' % name)
    fastly(ctx)

@task
def env(ctx, name):
    """`docker-machine env` with our machine path
    
    Run `eval $(invoke env nbviewer1)` to setup docker env for a given nbviewer instance
    
    Same as MACHINE_STORAGE_PATH=$PWD/machines docker-machine env <name>
    """
    ctx.run('docker-machine env %s' % name)


@task
def servers(ctx):
    """Print the names of current nbviewer servers"""
    for server in nbviewer_servers():
        print(server.name, server.access_ipv4)

def docker_machines(ctx):
    """Get list of docker-machine names"""
    return ctx.run('docker-machine ls -q', hide='out').stdout.split()

@task
def doitall(ctx):
    """Run a full upgrade from your laptop.
    
    This does:
    
    1. git pull
    2. upgrade on all machines
    """
    # make sure current repo is up to date
    ctx.run('git pull', echo=True)
    for machine in docker_machines(ctx):
        ctx.run("""
        set -e
        eval $(docker-machine env %s)
        invoke upgrade
        """ % machine, echo=True)
    fastly(ctx)

#------- Docker commands for running nbviewer --------

@lru_cache()
def docker_client():
    """Get a docker client instance"""
    docker = Client(**kwargs_from_env())
    return docker

@task
def nbcache(ctx):
    """Start the nbcache service"""
    run("docker run -d --label nbcache --name nbcache --restart always %s" % NBCACHE)

@task
def logentries(ctx):
    """Start the logentries log-forwarding service"""
    run("docker run -d --label logentries --name logentries --restart always "
        "-v /var/run/docker.sock:/var/run/docker.sock "
        "%s -t %s --no-stats -j -a host=%s" % (
            LOGENTRIES, creds['LOGENTRIES_TOKEN'],
            os.environ.get('DOCKER_MACHINE_NAME', socket.gethostname())
        )
    )

@task
def nbviewer(ctx, port=0, image='nbviewer'):
    """Start one nbviewer instance"""
    docker = docker_client()
    containers = docker.containers(filters={'label': 'nbcache'})
    if not containers:
        nbcache(ctx)
    containers = docker.containers(filters={'label': 'nbcache'})
    nbcache_id = containers[0]['Id']
    
    nbviewers = docker.containers(filters={'label': 'nbviewer'})
    ports_in_use = set()
    for c in nbviewers:
        for port_struct in c['Ports']:
            ports_in_use.add(port_struct['PublicPort'])
    
    if port == 0:
        port = 8080
        while port in ports_in_use:
            port += 1
    
    run(' '.join(map(pipes.quote, ['docker', 'run', '-d',
        '--env-file', 'env_file',
        '--label', 'nbviewer',
        '--restart', 'always',
        '--link', '%s:nbcache' % nbcache_id,
        '-p', '%i:8080' % port,
        '--name', 'nbviewer-%i' % port,
        image,
        'newrelic-admin', 'run-python',
        '-m', 'nbviewer',
        '--logging=info',
        '--port=8080',
        '--cache_expiry_min=3600',
        '--cache_expiry_max=14400',
    ])), echo=True)
    return port

@task
def pull(ctx, images=','.join([NBVIEWER, NBCACHE])):
    """Pull any updates to images from DockerHub"""
    for img in images.split(','):
        if '/' not in img:
            img = 'jupyter/' + img
        run('docker pull %s' % img)

@task
def build(ctx):
    """Build nbviewer image"""
    run('docker build -t nbviewer .')

@task
def bootstrap(ctx, n=2):
    """Set up a new cluster with nbcache, nbviewer"""
    pull(ctx)
    build(ctx)
    nbcache(ctx)
    logentries(ctx)
    ports = []
    for i in range(n):
        ports.append(nbviewer(ctx))
    print("Started %i nbviewer instances on ports %s" % (n, ports))

def wait_up(url):
    print("Waiting for %s" % url, end='')
    for i in range(30):
        try:
            requests.get(url)
        except Exception:
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1)
        else:
            print(".ok")
            return
    raise RuntimeError("nbviewer never showed up at %s" % url)

@task
def upgrade(ctx, yes=False):
    """Update images and redeploy
    
    NOTE: This destroys the old instances, so don't forget to download their logs first if you need them.
    """
    pull(ctx)
    build(ctx)
    docker = docker_client()
    containers = docker.containers(filters={'label': 'nbviewer'})
    if not yes:
        ans = ''
        q = "Are you sure? This will delete (including logs) %i containers [y/n]" % len(containers)
        while not ans.lower().startswith(('y','n')):
            ans = input(q)
        if ans.lower()[0] == 'n':
            return
    ports = []
    for running in containers:
        interface = running['Ports'][0]
        ip = interface['IP']
        if ip == '0.0.0.0':
            ip = ctx.run('docker-machine ip $(docker-machine active)', hide='out').stdout.strip()
        port = interface['PublicPort']
        id = running['Id']
        print("Relaunching %s at %s:%i" % (id[:7], ip, port))
        docker.stop(id)
        docker.remove_container(id)
        nbviewer(ctx, port)
        url = 'http://%s:%i' % (ip, port)
        wait_up(url)
        ports.append(port)
    print("Upgraded %i instances at %s" % (len(containers), ports))

@task
def restart(ctx):
    """Restart the current nbviewer instances"""
    docker = docker_client()
    containers = docker.containers(all=True, filters={'label': 'nbviewer'})
    for c in containers:
        short = c['Id'][:7]
        print("restarting %s" % short)
        docker.restart(c['Id'])

@task
def cleanup(ctx):
    """Cleanup stopped containers"""
    docker = docker_client()
    containers = docker.containers(filters={'label': 'nbviewer', 'status': 'exited'})
    if not containers:
        print("No containers to cleanup")
    for c in containers:
        id = c['Id']
        print("Removing %s" % id[:7])
        docker.remove_container(id)

@task
def statuspage(ctx):
    """Run the statuspage container. Only need one of these total."""
    docker = docker_client()
    stream = docker.build('statuspage', tag='nbviewer-statuspage', pull=True)
    for chunk in stream:
        for line in chunk.decode('utf8', 'replace').splitlines(True):
            info = json.loads(line)
            sys.stdout.write(info.get('stream', ''))
    containers = docker.containers(all=True, filters={'name': 'nbviewer-statuspage'})
    [ docker.remove_container(c['Id'], force=True) for c in containers ]
    run(' '.join(map(pipes.quote, ['docker', 'run',
        '-d', '-t',
        '--restart=always',
        '--env-file=env_file',
        '--env-file=env_statuspage',
        '--name=nbviewer-statuspage',
        'nbviewer-statuspage'
    ])))

#------- Fastly commands for updating the CDN --------

FASTLY_API = 'https://api.fastly.com'

class FastlyService:
    def __init__(self, api_key, service_id):
        self.session = requests.Session()
        self.session.headers['Fastly-Key'] = api_key
        self.service_id = service_id
        latest_version = self.versions()[-1]
        self.version = latest_version['number']
        if latest_version['active']:
            # don't have an inactive version yet
            self.api_request('/clone', method='PUT')
            latest_version = self.versions()[-1]
            self.version = latest_version['number']

    
    def api_request(self, path, include_version=True, method='GET', **kwargs):
        url = "{api}/service/{service_id}{v}{path}".format(
            api=FASTLY_API,
            service_id=self.service_id,
            v='/version/%i' % self.version if include_version else '',
            path=path,
        )
        r = self.session.request(method, url, **kwargs)
        try:
            r.raise_for_status()
        except Exception:
            print(r.text)
            raise
        return r.json()
    
    def backends(self):
        return self.api_request('/backend')
    
    def versions(self):
        return self.api_request('/version', include_version=False)
    
    def add_backend(self, name, hostname, port, copy_backend=None):
        if copy_backend is None:
            copy_backend = self.backends()[0]
        data = {
            key: copy_backend[key]
            for key in [
                'healthcheck',
                'max_conn',
                'weight',
                'error_threshold',
                'connect_timeout',
                'between_bytes_timeout',
                'first_byte_timeout',
                'auto_loadbalance',
                
            ]
        }
        data.update({
            'address': hostname,
            'name': name,
            'port': port,
        })
        self.api_request('/backend', method='POST', data=data)
    
    def remove_backend(self, name):
        self.api_request('/backend/%s' % name, method='DELETE')
    
    def deploy(self):
        # activate the current version
        self.api_request('/activate', method='PUT')
        # clone to a new version
        self.api_request('/clone', method='PUT')
        self.version = self.versions()[-1]['number']


def all_instances():
    """Return {(ip, port) : name} for all nbviewer containers on all machines"""
    all_nbviewers = {}
    docker_machine = Machine()
    for m in docker_machine.ls():
        name = m['Name']
        if not name:
            # weird bug where it gets an extra empty entry
            continue
        ip = docker_machine.inspect(name)['Driver']['IPAddress']
        docker = Client(**docker_machine.config(name))
        for c in docker.containers(filters={'label': 'nbviewer'}, all=True):
            port = c['Ports'][0]['PublicPort']
            all_nbviewers[(ip, port)] = '%s-%s' % (name, port)
    return all_nbviewers

@task
def fastly(ctx):
    """Update the fastly CDN"""
    print("Checking fastly backends")
    f = FastlyService(creds['FASTLY_KEY'], creds['FASTLY_SERVICE_ID'])
    changed = False
    backends = f.backends()
    nbviewers = all_instances()
    existing_backends = set()
    # first, delete the backends we don't want
    copy_backend = backends[0]
    for backend in backends:
        host = (backend['ipv4'], backend['port'])
        if host not in nbviewers:
            print("Deleting backend %s" % backend['name'])
            f.remove_backend(backend['name'])
            changed = True
        else:
            existing_backends.add(host)
    for host, name in nbviewers.items():
        if host not in existing_backends:
            ip, port = host
            print("Adding backend %s %s:%i", name, ip, port)
            f.add_backend(name, ip, port, copy_backend)
            changed = True

    if changed:
        print("Activating fastly configuration %s" % f.version)
        f.deploy()
    else:
        print("Fastly OK")

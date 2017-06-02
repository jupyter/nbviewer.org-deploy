#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Deploys nbviewer on docker

Two pieces:

First set of commands help setup nbviewer servers on Rackspace:

    servers, ssh, github_ssh, rsync, remote_upgrade, doitall

Second set are for deploying nbviewer with docker
(assumes docker env is already setup):

    build, pull, nbviewer, upgrade, bootstrap, etc.
"""

from __future__ import print_function

from datetime import date
from functools import lru_cache
import json
import os
import pipes
from subprocess import Popen, PIPE, check_output
import sys
import time

import requests
from invoke import run, task
from docker import APIClient as Client
from docker.utils import kwargs_from_env


NBVIEWER = 'jupyter/nbviewer'
NBCACHE = 'jupyter/nbcache'
HERE = os.path.dirname(os.path.abspath(__file__))

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
def github_ssh(ctx, usernames, servername=None):
    """Grant one or more user's GitHub ssh keys access to root on the given server
    
    servername can be a blob, so any matching server will grant access
    Default servername: 'nbviewer' so all nbviewer servers are
    """
    if not servername:
        servers = list(nbviewer_servers())
    else:
        servers = list(rackspace_client().compute.servers(name=servername))
    
    for username in usernames.split(','):
        _github_ssh(username, servers)


def _github_ssh(username, servers):
    # get keys from GitHub:
    r = requests.get('https://github.com/{}.keys'.format(username))
    r.raise_for_status()
    keys = r.content

    for server in servers:
        print("Giving {}@github SSH access to {} ({})".format(username, server.name, server.access_ipv4))
        ssh = ['ssh', 'root@%s' % server.access_ipv4]
        authorized_keys = check_output(ssh + ['cat /root/.ssh/authorized_keys']).decode('utf8', 'replace')
        if '@{}'.format(username) in authorized_keys:
            print("  {} already has access to {}".format(username, server.name))
            # TODO: instead of skipping found users, replace existing keys
            continue
        print("  Uploading {}'s keys".format(username))
        p = Popen(ssh + ['cat >> /root/.ssh/authorized_keys'], stdin=PIPE)
        p.stdin.write('# GitHub keys for @{} ({})\n'.format(username, date.today()).encode('utf8'))
        p.stdin.write(keys)
        if not keys.endswith(b'\n'):
            p.stdin.write(b'\n')
        p.stdin.close()
        p.wait()


@task
def ssh(ctx, name):
    """SSH to a rackspace server by name"""
    # match name exactly:
    exact_name = "^{}$".format(name)
    server = next(rackspace_client().compute.servers(name=exact_name), None)
    if server is None:
        ctx.exit("Server {} not found".format(name))
    print("SSHing to {} ({})".format(server.name, server.access_ipv4))
    ctx.run('ssh root@{}'.format(server.access_ipv4), pty=True, echo=True)


@task
def servers(ctx):
    """Print the names of current nbviewer servers"""
    for server in nbviewer_servers():
        print(server.name)

@task
def rsync(ctx):
    """Send the current state of this repo to nbviewer servers"""
    for server in nbviewer_servers():
        cmd = ['rsync', '-varuP', '--delete',
            HERE + '/',
            'root@{}:/srv/nbviewer-deploy/'.format(server.access_ipv4),
        ]
        ctx.run(' '.join(map(pipes.quote, cmd)), echo=True)


UPGRADE_SH = """
set -e
export PATH=/opt/conda/bin:$PATH
cd /srv/nbviewer-deploy
pip install --upgrade -r requirements.txt
invoke upgrade
"""

@task
def upgrade_remote(ctx):
    for server in nbviewer_servers():
        ctx.run('ssh root@{} "{}"'.format(server.access_ipv4, UPGRADE_SH), pty=True, echo=True)


@task
def doitall(ctx):
    """Run a full upgrade from your laptop.
    
    This does:
    
    1. git pull
    2. invoke rsync
    3. invoke upgrade_remote
    """
    # make sure current repo
    ctx.run('git pull', echo=True)
    rsync(ctx)
    upgrade_remote(ctx)

#------- Docker commands for running --------

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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Deploys nbviewer on docker

assumes Docker env is already set up, e.g. via

    source novarc
    eval `carina env nbviewer`
'''

from __future__ import print_function

import json
import pipes
import sys
import time

import requests
from invoke import run, task
from docker import APIClient as Client
from docker.utils import kwargs_from_env

NBVIEWER = 'jupyter/nbviewer'
NBCACHE = 'jupyter/nbcache'

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

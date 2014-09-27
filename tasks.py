#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Sets up a CoreOS cluster on rackspace, utilizing the CoreOS discovery service
to create a brand-spanking-new cluster.

This particular invokefile is tailored towards Notebook Viewer's deployment.

'''

import os
import requests
import tempfile

from invoke import run, task

token_get_url = "https://discovery.etcd.io/new"

################################################################################
# IMAGES! 
# 
#
# Image IDs likely to change, hardcoding for now because I'm just tinkering
# Any more advanced than this script and we should be using real provisioning
# tools
#
################################################################################
COREOS_ALPHA  = "78a24bc3-2545-433b-8067-a5143c04a3c3"
COREOS_BETA   = "746ba067-035c-4dbb-91f6-39300a7f8a03"
COREOS_STABLE = "4ca73331-5063-429f-8a27-70de5099e747"

# OnMetal images for CoreOS
COREOS_ONMETAL_ALPHA  = "f08e095c-9098-4a10-bbed-0394b40bb90f"
COREOS_ONEMTAL_BETA   = "87b95448-111f-4406-a048-6f12f93ead5d"
COREOS_ONMETAL_STABLE = "85e3d8d2-6d0f-4ded-bd55-0f13d3e57e69"

################################################################################
# FLAVORS!
#
# Get more flavors by visiting Baskin Robbins. Whoops, I mean by running
#   nova flavor-list
#
################################################################################
ONMETAL_COMPUTE = "onmetal-compute1"

FLAVORS = {
  "onmetal-compute1": {"Memory_MB": 32768,  "CPUs": 20},
  "onmetal-io1":      {"Memory_MB": 131072, "CPUs": 40},
  "onmetal-memory1":  {"Memory_MB": 524288, "CPUs": 24},
  "performance1-1":   {"Memory_MB": 1024,   "CPUs": 1},
  "performance1-2":   {"Memory_MB": 2048,   "CPUs": 2},
  "performance1-4":   {"Memory_MB": 4096,   "CPUs": 4},
  "performance1-8":   {"Memory_MB": 8192,   "CPUs": 8},
  "performance2-15":  {"Memory_MB": 15360,  "CPUs": 4},
  "performance2-30":  {"Memory_MB": 30720,  "CPUs": 8},
  "performance2-60":  {"Memory_MB": 61440,  "CPUs": 16},
  "performance2-90":  {"Memory_MB": 92160,  "CPUs": 24},
  "performance2-120": {"Memory_MB": 122880, "CPUs": 32},
}

# OnMetal compute + CoreOS Alpha
default_image = COREOS_ONMETAL_ALPHA
default_flavor = "onmetal-compute1"

default_image = COREOS_STABLE
default_flavor = "performance2-30"


#testing=True

#if(testing):
#    default_image = COREOS_STABLE
#    default_flavor = "performance2-15"

nova_template = '''nova boot \
           --image {image_id} \
           --flavor {flavor_id} \
           --key-name {key_name} \
           --user-data {user_data_file} \
           --config-drive true \
           {nodename}'''


cloud_config_template = '''#cloud-config
coreos:
  units:
    - name: nbcache.service
      enable: true
      content: |
        [Unit]
        Description=NotebookCache
        After=docker.service
        Requires=docker.service
        [Service]
        Restart=always
        ExecStartPre=/usr/bin/docker pull jupyter/nbcache
        ExecStart=/usr/bin/docker run --rm --name nbcache jupyter/nbcache
        ExecStop=/usr/bin/docker rm -f nbcache
        [Install]
        WantedBy=nbviewer.target
    - name: nbindex.service
      enable: true
      content: |
        [Unit]
        Description=NotebookIndex
        After=docker.service
        Requires=docker.service
        [Service]
        Restart=always
        ExecStartPre=/usr/bin/docker pull jupyter/nbindex
        ExecStart=/usr/bin/docker run --rm --name nbindex -v /mnt/nbindex/:/data -p 127.0.0.1:9200:9200 -p 127.0.0.1:9300:9300 jupyter/nbindex
        ExecStop=/usr/bin/docker rm -f nbindex
        [Install]
        WantedBy=nbviewer.target
    - name: nbviewer.1.service
      enable: true
      content: |
        [Unit]
        Description=NotebookViewer
        After=nbcache.service
        Requires=nbcache.service
        [Service]
        Restart=always
        ExecStartPre=/usr/bin/docker pull ipython/nbviewer
        ExecStart=/usr/bin/docker run --rm --name nbviewer.1.service -p 8081:8080 --link nbindex:nbindex --link nbcache:nbcache -e "GITHUB_OAUTH_KEY=8656da24f5727829853b" -e "GITHUB_OAUTH_SECRET=041402fb0a4f7f1ac87696e5a22892060408b415" ipython/nbviewer
        ExecStop=/usr/bin/docker rm -f %n
        [Install]
        WantedBy=nbviewer.target
    - name: nbviewer.2.service
      enable: true
      content: |
        [Unit]
        Description=NotebookViewer
        After=nbcache.service
        Requires=nbcache.service
        [Service]
        Restart=always
        ExecStartPre=/usr/bin/docker pull ipython/nbviewer
        ExecStart=/usr/bin/docker run --rm --name nbviewer.2.service -p 8082:8080 --link nbindex:nbindex --link nbcache:nbcache -e "GITHUB_OAUTH_KEY=8656da24f5727829853b" -e "GITHUB_OAUTH_SECRET=041402fb0a4f7f1ac87696e5a22892060408b415" ipython/nbviewer
        ExecStop=/usr/bin/docker rm -f %n
        [Install]
        WantedBy=nbviewer.target
write_files:
  - path: /etc/ssh/sshd_config
    permissions: 0644
    content: |
      UsePrivilegeSeparation sandbox
      Subsystem sftp internal-sftp
      PasswordAuthentication no
'''

@task
def bootstrap(node_name="nbviewer.ipython.org", key_name="main"):
    # OpenStack defaults for region, used for the fleet metadata
    region = os.environ.get("OS_REGION_NAME", os.environ.get("OS_REGION"))

    if region is None:
        raise Exception("$OS_REGION_NAME or $OS_REGION not set")

    # Total hack for user data, should probably be using the nova API or pyrax

    # This could easily be inside the loop if you need to create per node
    # configurations
    cloud_config = cloud_config_template.format()
    temp_cc = tempfile.NamedTemporaryFile("w", delete=False)
    temp_cc.write(cloud_config)
    temp_cc.close()

    node(node_name, user_data=temp_cc.name, key_name=key_name)

    os.remove(temp_cc.name)

@task
def node(nodename="corenode",
         user_data="./cloud_config.yml",
         key_name="main",
         image_id=default_image,
         flavor_id=default_flavor):

    nova_line = nova_template.format(nodename=nodename,
                                     image_id=image_id,
                                     flavor_id=flavor_id,
                                     user_data_file=user_data,
                                     key_name=key_name)

    run(nova_line)



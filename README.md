# nbviewer-deploy

Tasks for running nbviewer in docker, with [invoke](http://pyinvoke.org).

The tasks have two categories:

1. managing nbviewer servers on rackspace (run from your laptop), and
2. launching/upgrading nbviewer itself in docker (run on the remote via docker-machine)

## Quickstart: upgrading nbviewer

First, get what you need to run the invoke tasks:

    pip install -r requirements.txt

Assuming you have access to everything,
publishing the latest version of nbviewer can be done with one command from this repo:

    invoke doitall

This will:

    1. `git pull`
    2. `invoke upgrade` on each nbviewer instance, via docker-machine

There will be a confirmation prompt once it gets to the destructive action of destroying previous containers and starting new ones.

## Current deployment

Right now, nbviewer is run on Rackspace servers on the Jupyter account, with the names 'nbviewer-N'.

On each server, there are two nbviewer workers and one memcache instance. One server is additionally running the statuspage daemon to send stats to https://status.jupyter.org,
started with

    invoke statuspage

## Dependencies

Python dependencies:

    pip install -r requirements.txt


## Managing nbviewer servers

nbviewer servers are hosted on Rackspace and
The credentials are stored in this repo in the `machine` directory.

There are a few commands that can be run from your laptop,
to help with managing nbviewer servers.
The rest talk to docker directly, and should be run after setting up your docker env for a given node:

    eval $(invoke env nbviewer-3)

To see the names and ips of current nbviewer servers:

    invoke servers


## Running nbviewer with docker

The commands below talk to docker directly, and are to be run with access
to docker, either directly or via `docker-machine`.

### Booting from scratch

Assuming docker is set up, run

```
invoke bootstrap -n 2
```

to start a new deployment of nbviewer with two instances.


### Upgrading

To upgrade the deployment in-place:

```
invoke upgrade
```

This will pull new images from DockerHub, take down containers one at a time, and bring new ones up in their places.

TODO: we should actually bring up new nodes on *new* ports and add them to fastly before removing the old ones.

### Restart

To relaunch the current instances without any other changes:

```
invoke restart
```


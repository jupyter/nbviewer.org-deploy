# nbviewer-deploy

Tasks for running nbviewer in docker, with [invoke](http://pyinvoke.org).

The tasks have two categories:

1. managing nbviewer servers on rackspace (run from your laptop), and
2. launching/upgrading nbviewer itself in docker (run on the remote)

## Quickstart: upgrading nbviewer

First, get what you need to run the invoke tasks:

    pip install -r requirements.txt

Assuming you have access to everything,
publishing the latest version of nbviewer can be done with one command from this repo:

    invoke doitall

This will:

    1. `git pull`
    2. `invoke rsync` to send the current repo to our nbviewer servers
    3. `invoke upgrade_remote` to run `invoke upgrade` on the remote machines via `ssh`

There will be a confirmation prompt once it gets to the destructive action of destroying previous containers and starting new ones.

## Current deployment

Right now, nbviewer is run on Rackspace servers on the Jupyter account, with the names 'nbviewer-1' and 'nbviewer-2'.

Two steps are **not automated**:

- Launching new nbviewer servers. This can be done via the rackspace API, but is not yet automated.
  To launch a new server:
  
  1. create a new server via rackspace dashboard with the name 'nbviewer-N'
  2. install docker (follow Docker's own instructions)
  3. clone this repo in `/srv/nbviewer-deploy`
  4. setup letsencrypt (TODO: docs)
- Load-balancing is handled in fastly. If a new nbviewer instance is added, fastly must be
  told manually about the new host. Fastly has an API, so this can be automated in the future, but
  is not yet.

On each server, there are two nbviewer workers and one memcache instance. One server is additionally running the statuspage daemon to send stats to https://status.jupyter.org.

## Dependencies

Python dependencies:

    pip install -r requirements.txt


## Managing nbviewer servers

There are a few commands that can be run from your laptop,
to help with managing nbviewer servers.
The rest talk to docker directly, and should be run directly on the nbviewer servers.

To give another person access to the nbviewer servers,
you can add their GitHub SSH keys with:

    invoke github_ssh username

To see the names of current nbviewer servers:

    invoke servers

To ssh to a particular nbviewer server:

    invoke ssh nbviewer-2

To rsync the current nbviewer-deploy repo to nbviewer servers:

    invoke rsync


## Running nbviewer with docker

The commands below talk to docker directly, and are to be run with access
to docker, either directly or via `docker-machine`.
With the current setup, this means they would be run on the nbviewer servers.

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

This will pull new images from DockerHub, take down nodes one at a time, and bring new ones up in their places.

TODO: we should actually bring up new nodes on *new* ports and add them to fastly before removing the old ones.

### Restart

To relaunch the current instances without any other changes:

```
invoke restart
```


## TODO

Improvements I would like to see:

- script fastly API, so that old instances don't need to be destroyed before creating new ones
- script creation of new machines with `docker-machine`,
  which would remove the `ssh` part because all docker commands could be executed locally
  (like it was when we used `carina`).

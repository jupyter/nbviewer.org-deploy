# nbviewer.org-deploy

Tasks for running nbviewer.jupyter.org in helm, with [invoke](http://pyinvoke.org).

TODO: helm commands have not yet been implemented.

## Quickstart: upgrading nbviewer

First, get what you need to run the invoke tasks:

    pip install -r requirements.txt

Assuming you have access to everything,
publishing the latest version of nbviewer can be done with one command from this repo:

    invoke doitall

This will: TODO

1. `git pull`
2. `invoke upgrade` on each nbviewer instance, via docker-machine

There will be a confirmation prompt once it gets to the destructive action of destroying previous containers and starting new ones.

## Current deployment

Right now, nbviewer is run on OVHCloud via helm in the namespace `nbviewer`.

## Dependencies

Python dependencies:

    pip install -r requirements.txt


### Upgrading

To upgrade the deployment in-place:

```
invoke upgrade
```

This will deploy the new helm configuration

## TODO

- Fastly is scripted now, but we could do better.
  Load-balancer DNS/ip is hardcoded in tasks.py and must be updated if changed.
  See the output of `kubectl get svc` for the current ip address,
  and update with `invoke fastly`.

- cdn.jupyter.org is proxied through Cloudflare DNS.
  Changes to ip require manual update at https://

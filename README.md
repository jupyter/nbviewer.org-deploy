# nbviewer.org-deploy

Tasks for running nbviewer.org in helm, with [invoke](http://pyinvoke.org).

**TODO: helm automatiion have not yet been implemented,
but are current run via `deploy.sh`.
This assumes the `nbviewer` repo is adjacent to this repo
and up-to-date.**

## Quickstart: upgrading nbviewer

Currently assumes you have helm, kubectl

1. clone nbviewer: `git clone https://github.com/jupyter/nbviewer`
2. clone this repo: `git clone https://github.com/jupyter/nbviewer.org-deploy`
3. Run helm upgrade `cd nbviewer.org-deploy; bash deploy.sh`

**NOTE: The invoke tasks.py has not been updated**

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
  Changes to ip require manual update at https://dash.cloudflare.com/dns.

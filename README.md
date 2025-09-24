# nbviewer.org-deploy

Deployment repo for nbviewer.org

## Overview

The nbviewer image and helm chart are defined in https://github.com/jupyter/nbviewer.
The helm chart in that repo is not _published_ anywhere,
so we use a local checkout.
Helm upgrades are deployed via GitHub actions.

Some _very_ infrequent manual tasks (interacting with the fastly cache layer) are scripted in `tasks.py` for use with `pyinvoke`.
We're mostly trying to move away from that, but tasks are infrequent enough.
Let's not add to them, though.

## Automation

- helm upgrade happens when PRs are merged in `.github/workflows/cd.yml`
- The nbviewer repo is automatically checked for updates in `.github/workflows/watch-dependencies`

## Quickstart: upgrading nbviewer

nbviewer publishes its images automatically.
If a change you want to deploy was merged recently,
make sure to wait for the image to be published to Docker Hub
(takes a few minutes).

Checking for nbviewer updates and deploying to nbviewer.org is done automatically every day.

To manually run a check for the latest version of nbviewer, run the [watch-dependencies](https://github.com/jupyter/nbviewer.org-deploy/actions/workflows/watch-dependencies.yaml) action.
This should open a PR with any changes.

You can also check for updates manually with `python3 scripts/update-nbviewer.py`, and open a PR yourself.

When that PR is merged, the updated nbviewer will be deployed.

### Upgrading details

The nbviewer version is current in two places:

- the _chart_ version in `.github/workflows/cd.yml`
- the _image_ version in `config/nbviewer.yaml`

To deploy an update from nbviewer to nbviewer.org:

1. check the latest version of the nbviewer repo (https://github.com/jupyter/nbviewer/commits)
2. store the latest commit in `NBVIEWER_VERSION` in [.github/workflows/cd.yaml](.github/workflows/cd.yml)
3. check the latest tag of the [nbviewer image](https://hub.docker.com/r/jupyter/nbviewer/tags)
4. update the tag in [config/nbviewer.yaml](config/nbviewer.yaml)

These steps are scripted in `scripts/update-nbviewer.py`.

Open a pull request, and it should be deployed to nbviewer.org upon merge.

## Current deployment

Right now, nbviewer is run on OVHCloud via helm in the namespace `nbviewer`.

## Dependencies

Python dependencies:

    pip install -r requirements.in # (or requirements.txt for a locked env)

## TODO

- Fastly is scripted now, but we could do better.
  Load-balancer DNS/ip is hardcoded in tasks.py and must be updated if changed.
  See the output of `kubectl get svc` for the current ip address,
  and update with `invoke fastly`.

- cdn.jupyter.org is proxied through Cloudflare DNS.
  Changes to ip require manual update at https://dash.cloudflare.com/dns.

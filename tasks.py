#!/usr/bin/env python3
"""
Deploys nbviewer on helm

"""

import requests
from invoke import task

creds = {}
with open("creds") as f:
    exec(f.read(), creds)


@task
def trigger_build(ctx):
    url_base = "https://hub.docker.com/api/build/v1/source/579ab043-912f-425b-8b3f-765ee6143b53/trigger/{}/call/"
    r = requests.post(url=url_base.format(creds["DOCKER_TRIGGER_TOKEN"]))
    r.raise_for_status()
    print(r.text)


@task
def doitall(ctx):
    """Run a full upgrade from your laptop.

    This does:

    1. git pull
    2. upgrade on all machines
    """
    # make sure current repo is up to date
    ctx.run("git pull", echo=True)
    upgrade(ctx)
    fastly(ctx)


@task
def upgrade(ctx, yes=False):
    """Update helm deployment"""
    raise NotImplementedError("Not implemented yet for helm")


# ------- Fastly commands for updating the CDN --------

FASTLY_API = "https://api.fastly.com"


class FastlyService:
    def __init__(self, api_key, service_id):
        self.session = requests.Session()
        self.session.headers["Fastly-Key"] = api_key
        self.service_id = service_id
        latest_version = self.versions()[-1]
        self.version = latest_version["number"]
        if latest_version["active"]:
            # don't have an inactive version yet
            self.api_request("/clone", method="PUT")
            latest_version = self.versions()[-1]
            self.version = latest_version["number"]

    def api_request(self, path, include_version=True, method="GET", **kwargs):
        url = "{api}/service/{service_id}{v}{path}".format(
            api=FASTLY_API,
            service_id=self.service_id,
            v=f"/version/{self.version}" if include_version else "",
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
        return self.api_request("/backend")

    def versions(self):
        return self.api_request("/version", include_version=False)

    def add_backend(self, name, hostname, port, copy_backend=None):
        if copy_backend is None:
            copy_backend = self.backends()[0]
        data = {
            key: copy_backend[key]
            for key in [
                "healthcheck",
                "max_conn",
                "weight",
                "error_threshold",
                "connect_timeout",
                "between_bytes_timeout",
                "first_byte_timeout",
                "auto_loadbalance",
            ]
        }
        data.update({"address": hostname, "name": name, "port": port})
        self.api_request("/backend", method="POST", data=data)

    def remove_backend(self, name):
        self.api_request(f"/backend/{name}", method="DELETE")

    def deploy(self):
        # activate the current version
        self.api_request("/activate", method="PUT")
        # clone to a new version
        self.api_request("/clone", method="PUT")
        self.version = self.versions()[-1]["number"]


def all_instances():
    """Return {(ip, port) : name} for all running nbviewer containers on all machines"""
    all_nbviewers = {}
    # add ovh by hand
    # TODO: get service from kubernetes
    all_nbviewers[("135.125.83.237", 80)] = "ovh"
    return all_nbviewers


@task
def fastly(ctx):
    """Update the fastly CDN"""
    print("Checking fastly backends")
    f = FastlyService(creds["FASTLY_KEY"], creds["FASTLY_SERVICE_ID"])
    changed = False
    backends = f.backends()
    nbviewers = all_instances()
    existing_backends = set()
    # first, delete the backends we don't want
    copy_backend = backends[0]
    for backend in backends:
        host = (backend["address"], backend["port"])
        if host not in nbviewers:
            print(f"Deleting backend {backend['name']}")
            f.remove_backend(backend["name"])
            changed = True
        else:
            existing_backends.add(host)
    for host, name in nbviewers.items():
        if host not in existing_backends:
            ip, port = host
            print(f"Adding backend {name} {ip}:{port}")
            f.add_backend(name, ip, port, copy_backend)
            changed = True

    if changed:
        print(f"Activating fastly configuration {f.version}")
        f.deploy()
    else:
        print("Fastly OK")

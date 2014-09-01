nbviewer-deploy
===============

All the bits to put nbviewer in the cloud

Structural differences from our previous setup:

* Main system is [CoreOS](https://coreos.com/)
* We're using [bare metal](http://www.rackspace.com/cloud/servers/onmetal/) + [Docker containers](https://www.docker.com/)
* The memcached instance is shared amongst the N instances of the Notebook Viewer app
* Starting from scratch involves the use of the invokefile (tasks.py)

### Booting from scratch

Assuming the right OpenStack/Rackspace environment variables are set, simply run

```
invoke bootstrap
```

### Tool suite

Now that we're on CoreOS, I suggest getting familiar with systemctl (systemd) and journalctl.

#### Tailing the logs

```
journalctl -f
```


#### Restart app servers

```
sudo systemctl restart nbviewer.1.service
sudo systemctl restart nbviewer.2.service
```


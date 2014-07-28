nbviewer-deploy
===============

All the bits to put nbviewer in the cloud

Structural differences from our previous setup:

* Main system is [CoreOS](https://coreos.com/)
* We're using [bare metal](http://www.rackspace.com/cloud/servers/onmetal/) + [Docker containers](https://www.docker.com/)
* The memcached instance is shared amongst the N instances of the Notebook Viewer app
* Starting from scratch involves the use of the invokefile (tasks.py)

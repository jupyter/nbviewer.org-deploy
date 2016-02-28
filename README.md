# nbviewer-deploy

Tasks for running nbviewer in docker

### Dependencies

- [carina](https://getcarina.com/docs/getting-started/getting-started-carina-cli/)
- Python dependencies:

       pip install -r requirements.txt


### Setting your env

Make sure you have your docker env set up, for instance:

```
source creds
eval `carina env nbviewer`
```

### Booting from scratch

Assuming the right docker environment is set above, run

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


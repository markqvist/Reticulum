# Docker Images

Docker resources Reticulum service and tooling

## End-user

As an end-user you can make use of the `Dockerfile` to create a simple docker image based on the latest `rns` package available in [PyPi](https://pypi.org/project/rns/)

### Building

To build the image:

- Copy the `Dockerfile` to a directory and in that directory run:
  - `docker build -t reticulum:latest .`

- From the root of this repository run:
  - `docker build -t reticulum:latest -f docker/Dockerfile .`

### Running

#### Docker Run
You can run the container in various ways, a quick way to test would be interactively:

- Create a directory to hold the configuration and other files - `mkdir config`
- Start the container - `docker run --rm --name reticulum -v ./config:/config -it reticulum:latest`

This will create a container named `reticulum`, mount the config directory to the directory you created above in your current working directory (`./config`) and automatically delete que container (`--rm`) when you detach from the session (files in the config directory will be retained)

You can edit the config file at `./config/config` to configure rns as usual

Once the container is running, you can use other rns tools via `docker exec`:

`docker exec -it reticulum rnpath`


#### Docker Compose

You can also use the included example `docker-compose.yml` file to manage the container in a more automated way. It has some comments but if you are not familiar with it, it is probably a good idea to read the [official `docker compose` docs](https://docs.docker.com/compose/)


## Developer

The file `Dockerfile.dist` is meant to be used for CI, its similar to the end-user Dockerfile except that it will grab and install wheel files from the `/dist` directory instead
This could be used in this order:
- `make build_wheel`
- Build the container with `Dockerfile.dist`
  - Via github workflows
  - Manually `docker build -t reticulum:latest -f docker/Dockerfile.dist .`

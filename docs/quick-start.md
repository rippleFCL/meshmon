# Quick start

this guide assumes that you have 3 machines that will be referenced as so `node-1`, `node-2`, and `node-3`


### Create Project Structure
On every machines run to setup the project structure
```bash
mkdir -p meshmon/config/networks/local
```


### Node Configuration
In `meshmon/config/nodeconf.yml` on each machine add the node config

On machine `node-1`
```yml
networks:
  - directory: local
    node_id: node-1
```

On machine `node-2`
```yml
networks:
  - directory: local
    node_id: node-2
```

On machine `node-3`
```yml
networks:
  - directory: local
    node_id: node-3
```


### Network Configuration
In `meshmon/config/networks/local/config.yml` on each machine add:

```yml
network_id: local-network
node_config:
  - node_id: node-1
    url: <replaceme>:42069
  - node_id: node-2
    url: <replaceme>:42069
  - node_id: node-3
    url: <replaceme>:42069
```

### Docker Compose
In `meshmon/docker-compose.yml` on each machine add:

```yml
services:
  node:
    image: ghcr.io/ripplefcl/meshmon:latest
    ports:
      - 8000:8000 #Web ui
      - 42069:42069 #Grpc
    volumes:
      - ./config:/app/config
    restart: unless-stopped
```

### Bring up Stack
Run on each machine:
```bash
cd meshmon && docker compose up
```

!!! info "There will be errors and/or warnings"
    Keep in mind that bringing a cluster up in this state will cause errors/warnings in the console. This is due to each node not knowing the public keys of the other nodes.

### Authentication
Each node in MeshMon has a public/private key that is used to verify messages originating from remote nodes. For local configs these public keys need to be manually copied over.

!!! info "There must be a better way to do this!!"
    There is! Check out [Config Management](configuration/config-managment.md#2-git-centralized-repository).

Inside `meshmon/config/networks/local/pubkeys/` on each machine, you will find the public key for each node. Copy each public key to every other machine.

After the copy operation your `meshmon/config/networks/local/pubkeys/` should look the same on every node.

Target file structure:

```
pubkeys/
  node-1.pub    # public key for node-1
  node-2.pub    # public key for node-2
  node-3.pub    # public key for node-3
```

!!! note ""
    The pubkey filenames must exactly match the node_id values with a .pub suffix.

### Done
Theres no need to restart the container as it will hot reload the new config.


## Further reading
Congrats you now have a multi-node Meshmon cluster!

For adding monitors see [this](configuration/network.md#monitors)

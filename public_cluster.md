
## Joining the Public Meshmon Cluster

You can join the public meshmon cluster to participate in a global, open monitoring network. The public cluster configuration is maintained at [rippleFCL/meshmon-public-network](https://github.com/rippleFCL/meshmon-public-network).

### Steps to Join

1. **Clone the Public Network Repository**

	```bash
	git clone https://github.com/rippleFCL/meshmon-public-network.git
	```

2. **Configure Your Node**

	In your `config/nodeconf.yml`, add the public network as follows:

	```yaml
	networks:
	  - directory: meshmon-public-network
		 node_id: <your-unique-node-id>
		 config_type: git
		 git_repo: https://github.com/rippleFCL/meshmon-public-network.git
	```

	- Replace `<your-unique-node-id>` with a unique identifier for your node.

3. **Generate Your Node Keys**

	On first run, meshmon will generate your Ed25519 key pair and place your public key in the appropriate directory. If you want your node to be recognized by others, submit your public key as a pull request to the public network repository:

	- Copy your public key (e.g., `config/.public_keys/meshmon-public-network/<your-node-id>.pub`)
	- Fork the repository, add your key to `pubkeys/`, and open a pull request.

4. **Run Meshmon**

	Start your meshmon node as usual (see Quick Start in the main README). Meshmon will automatically sync the public network configuration and begin monitoring other nodes in the cluster. You can now view your webui.

### Notes

- The public cluster uses Git-based configuration, so your node will periodically pull updates from the repository.
- For Discord webhook notifications, set the `discord_webhook` field in your node configuration if desired.

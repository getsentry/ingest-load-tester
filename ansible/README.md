# Ansible Configuration for Load Test Infrastructure

This directory contains Ansible playbooks and roles for managing a locust across
a cluster of VMs

## Structure

```
├── ansible.cfg                 # Ansible configuration
├── inventory/
│   └── hosts.yml              # Inventory file with master and worker hosts
├── site.yml                   # Main playbook
└── roles/
    ├── common/                # Common tasks for all hosts
    │   └── tasks/
    │       └── main.yml       # Install Python3 and pip
    ├── master/                # Master node configuration
    │   ├── tasks/
    │   │   └── main.yml       # Deploy and configure master
    │   ├── templates/
    │   │   └── locust-master.service.j2
    │   └── handlers/
    │       └── main.yml
    └── worker/                # Worker node configuration
        ├── tasks/
        │   └── main.yml       # Deploy and configure workers
        ├── templates/
        │   └── locust-worker.service.j2
        └── handlers/
            └── main.yml
```

## Host Groups

- **master**: Manages the load test workload and provides the web UI
- **workers**: Connect to the master to execute distributed load tests

## Prerequisites

1. Provision several VMs to run locust on. You'll need one master, and several workers.
2. Add each host to your `/etc/hosts` file as ansible uses hostnames.
3. Open port 5557 on the master so that workers can connect to the master.

4. ```bash
   gcloud compute firewall-rules create locust-master-port --action=ALLOW --direction=INGRESS --rules=tcp:5557 --network sbx--stream-1-network --source-ranges=0.0.0.0/0
   ```

4. Install Ansible on your local machine:
   ```bash
   pip install ansible
   ```

5. Ensure SSH access to all hosts:
   ```bash
   ssh-copy-id user@host
   ```

6. Update `inventory/hosts.yml` with the correct `ansible_user` if different from your local username

## Usage

The easiest way to run Ansible is through the provided Makefile targets from the project root:

### Deploy to all hosts

```bash
make ansible-all
```

### Deploy only to master

```bash
make ansible-master
```

### Deploy only to workers

```bash
make ansible-workers
```

### Check connectivity

```bash
make ansible-ping
```

### Using Tags

Run only specific tasks using the TAGS variable:

```bash
# Only deploy application files
make ansible-all TAGS=deploy

# Only configure services
make ansible-all TAGS=service

# Run multiple tags
make ansible-all TAGS=deploy,config

# Deploy only to master with specific tags
make ansible-master TAGS=deploy,service
```

### Available Tags

```bash
make ansible-tags
```

Tags available:
- `packages` - Install system packages
- `python` - Python and pip setup
- `deploy` - Deploy application files
- `config` - Configure services
- `service` - Manage systemd services
- `master` - Master-specific tasks
- `worker` - Worker-specific tasks

### Direct Ansible Commands

You can also run Ansible directly from the ansible directory:

```bash
cd ansible

# Deploy to all hosts
ansible-playbook site.yml

# Deploy only to master
ansible-playbook site.yml --limit master

# Deploy with tags
ansible-playbook site.yml --tags deploy,config

# Check connectivity
ansible all -m ping
```

### Add new workers

Edit `inventory/hosts.yml` and add new hosts under the `workers` group:

```yaml
workers:
  hosts:
    worker-01:
      ansible_host: 10.0.148.115
    worker-02:
      ansible_host: 10.0.148.116
```

Then run the playbook to configure the new workers:

```bash
ansible-playbook site.yml --limit workers
```

## What Gets Installed

### All Hosts (common role)
- Python 3
- pip for Python 3

### Master Node
- Application code in `/opt/ingest-load-tester`
- Python virtual environment with dependencies
- systemd service running Locust in master mode
- Web UI accessible on port 8089

### Worker Nodes
- Application code in `/opt/ingest-load-tester`
- Python virtual environment with dependencies
- systemd service running Locust in worker mode
- Automatically connects to the master node

## Managing Services

### Check service status

```bash
ansible master -m shell -a "systemctl status locust-master"
ansible workers -m shell -a "systemctl status locust-worker"
```

### Restart services

```bash
# Using Makefile targets (only restart services, don't redeploy)
make ansible-all TAGS=service

# Or direct ansible commands
cd ansible
ansible master -m systemd -a "name=locust-master state=restarted"
ansible workers -m systemd -a "name=locust-worker state=restarted"
```

### View logs

```bash
cd ansible
ansible master -m shell -a "journalctl -u locust-master -n 50"
ansible workers -m shell -a "journalctl -u locust-worker -n 50"
```

## Customization

- Modify the locust file used by editing the systemd service templates
- Adjust the number of expected workers in `roles/master/templates/locust-master.service.j2`
- Configure additional environment variables or settings in the service files

# Install k8s cluster
Down load source from git: https://github.com/ghostWood1071/k8s-data-cluster.git

    git clone https://github.com/ghostWood1071/k8s-data-cluster.git
 This setup apply for 9 machines:

 - [ ] 3 machines for k8s cluster  
 - [ ] 3 machines for starrock cluster  
 - [ ] 3 machines for minio cluster

## Cloud deployment

    cd k8s-data-cluster/setup-cluster
Change resource in file *terraform.tfvars*

    minio_instance_type = "t3.medium"  
    svc_instance_type = "t3.xlarge"  
    starrock_instance_type = "t3.large"
Change storage in file terraform.tfvars

    minio_data_size_gb = 2048  
    svc_data_size_gb = 1024  
    minio_gp3_iops = 6000  
    minio_gp3_throughput = 500  
    svc_gp3_iops = 4000  
    svc_gp3_throughput = 250  
    starrock_size_gb = 100

 Create AWS credential 

    aws configure
Apply change to AWS

    terraform init
    terraform plan
    terraform apply

## Physical machine deployment

If install in physical machine please run .sh files from folder: *k8s-data-cluster/setup-cluster/scripts:

    ./common.sh #install k8s to machine
    ./master.sh #install additional packkages to master machine
 Install calico network

     kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.3/manifests/calico.yaml

## Join all workers
On master node: 

    kubeadm token create --print-join-command
Result from above command like:

    kubeadm join <master_ip>:6443 --token <token> --discovery-token-ca-cert-hash <sha256>
Paste this command to worker machines:
		sudo kubeadm join <master_ip>:6443 --token <token> --discovery-token-ca-cert-hash <sha256>
Verify the join:

    kubectl get node -A -o wide

Then, we have 2 k8s clusters, 1 for MinIO, 1 for data cluster
We will not deploy Starrock by k8s

## Deploy tools to data cluster
Move to folder *k8s-data-services/k8s*

    cd ../k8s-data-services/k8s
  Install Helm
  

    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

Create namespaces

    kubectl apply -f 00.namespace.yaml
  
  Apply secret config and service account
  

    kubectl apply -f 01-secrets-configs
Deploy metastore service (hive + postgres)

    kubectl apply -f metastore
Deploy orchestration service (postgres + airflow)

    cd ./orchestration
    kubectl apply -f storage.yaml
    helm repo add apache-airflow https://airflow.apache.org
    helm install airflow apache-airflow/airflow -n orchestration -f values.yaml
 ✍Use file Docker file in hive folder to build custom image

## Deploy MinIO
Change to Minio cluster

    kubectl apply -f storage
## Deploy Starrock
Install Java 11 on 3 machines
    sudo apt update
	sudo apt install openjdk-11-jdk
Edit .bashrc file to export JAVA_HOME and edit PATH variable

    nano .bashrc
Insert this to .bashrc file in 3 machines:

	export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
	export PATH="${JAVA_HOME}/bin:${PATH}"
Apply change:
	

    source ~/.bashrc
Download Starrock installation files in 3 machines:

    wget https://releases.starrocks.io/starrocks/StarRocks-3.3.19-ubuntu-amd64.tar.gz
    tar -xzvf StarRocks-3.3.19-ubuntu-amd64.tar.gz
    mv StarRocks-3.3.19-ubuntu-amd64 starrocks
Create metadata and data folder for FE and BE in 3 machines:

     sudo mv starrocks /opt/starrocks  
     sudo mkdir -p /data/starrocks/meta
     sudo mkdir -p /data/starrocks/storage
     sudo mkdir -p /data/starrocks/meta
Edit /opt/starrocks/fe/conf/fe.conf in 3 machines, insert 3 line below:

	    priority_networks = <ip_machine_1> <ip_machine_2> <ip_machine_3>
	    JAVA_HOME = /usr/lib/jvm/java-11-openjdk-amd64
	    meta_dir = /data/starrocks/meta

> *priority_networks look like this:  * `priority_networks = 172.31.34.95/20 172.31.39.190/20 172.31.41.40/20`

Edit /opt/starrocks/be/conf/be.conf in 3 machines, insert 3 row below:

	    storage_root_path = /data/starrocks/storage
	    priority_networks = priority_networks = <ip_machine_1> <ip_machine_2> <ip_machine_3>
	    JAVA_HOME = /usr/lib/jvm/java-11-openjdk-amd64 

> *priority_networks look like this:  * `priority_networks = 172.31.34.95/20 172.31.39.190/20 172.31.41.40/20`

Grant permission to execution files in 3 machines:

	    chmod +x /opt/starrocks/be/bin/start_be.sh
	    chmod +x /opt/starrocks/fe/bin/start_fe.sh
Run BE in 3 machines:

	    sudo su
	    /opt/starrocks/be/bin/start_be.sh --daemon
Run FE in master node:

    sudo su
    /opt/starrocks/fe/bin/start_fe.sh --daemon
In master node run this:

    mysql -h <IP_FE_leader> -P9030 -uroot
Then run sql commands:

	    ALTER SYSTEM ADD BACKEND "<ip_node_1>:9050", "<ip_node_2>:9050";
	    ALTER SYSTEM ADD FOLLOWER "<ip_node_1>:9010";
	    ALTER SYSTEM ADD FOLLOWER "<ip_node_2>:9010";
	    
In 2 worker node run this command:

    /opt/starrocks/fe/bin/start_fe.sh --helper <master_node>:9010 --daemon


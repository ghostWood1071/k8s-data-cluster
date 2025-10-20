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

## Deploy MinIO
Change to Minio cluster

    kubectl apply -f storage
## Deploy Starrock

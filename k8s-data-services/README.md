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
## Deploy volume manager (Longhorn)
### Prerequisites (run on all nodes)

Enable required services

    sudo systemctl enable containerd kubelet iscsid multipathd

Fix multipathd conflict with Longhorn iSCSI

    sudo bash << 'EOF'
    cat > /etc/multipath.conf << 'MEOF'
    defaults {
        user_friendly_names yes
    }
    blacklist {
        devnode "^sd[a-z0-9]+"
    }
    MEOF
    systemctl restart multipathd
    EOF

Install iSCSI and NFS client

    sudo apt update && sudo apt install -y open-iscsi nfs-common
    sudo systemctl enable --now iscsid

### Install Longhorn

    cd ./volume-manager
    helm repo add longhorn https://charts.longhorn.io
    helm install longhorn longhorn/longhorn -n volume-manager --version 1.11.1 -f values.yaml
## Deploy metastore services (hive + postgres)

    kubectl apply -f metastore
## Deploy orchestration services (postgres + airflow)
    cd ./orchestration
    kubectl apply -f storage.yaml
    helm repo add apache-airflow https://airflow.apache.org
    helm install airflow apache-airflow/airflow -n orchestration -f values.yaml
 📌Use file Docker file in hive folder to build custom image
 
 📌After install grant permission to airflow's volumes
 
    sudo mkdir -p /data/airflow/dags/
    sudo mkdir -p /data/airflow/logs/
    sudo mkdir -p /data/airflow/postgres
    sudo chmod -R 777 /data/airflow/postgres
    sudo chmod -R 777 /data/airflow/dags
    sudo chmod -R 777 /data/airflow/logs
    
    kubectl patch pvc data-airflow-postgresql-0 -n orchestration --type=merge -p '{"spec":{"volumeName":"pv-airflow-postgres"}}'

    kubectl patch pvc airflow-dags -n orchestration --type=merge -p '{"spec":{"volumeName":"pv-airflow-dags"}}'

    kubectl patch pvc airflow-logs -n orchestration --type=merge -p '{"spec":{"volumeName":"pv-airflow-logs"}}'
    
    kubectl patch pvc airflow-logs -n orchestration -p '{"spec":{"storageClassName":"hostpath"}}'
    
    kubectl patch pvc airflow-dags -n orchestration -p '{"spec":{"storageClassName":"hostpath"}}'
    
    kubectl patch pvc data-airflow-postgresql-0 -n orchestration -p '{"spec":{"storageClassName":"hostpath"}}'

## Deploy MinIO
Change to Minio cluster

    kubectl apply -f storage
## Deploy Starrocks

    helm repo add starrocks https://starrocks.github.io/starrocks-kubernetes-operator
	helm repo update
	kubectl create secret generic starrocks-root-pass --from-literal=password='g()()dpa$$word' -n warehouse
	helm install starrocks starrocks/kube-starrocks -f values.yaml -n warehouse --create-namespace
	helm uninstall starrocks -n warehouse
	helm upgrade --install starrocks starrocks/kube-starrocks -n warehouse --create-namespace -f values.yaml
    kubectl patch pvc fe-log-kube-starrocks-fe-0 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-fe-logs-0", "storageClassName":"hostpath"}}'
	kubectl patch pvc fe-log-kube-starrocks-fe-1 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-fe-logs-1", "storageClassName":"hostpath"}}'
	kubectl patch pvc fe-meta-kube-starrocks-fe-0 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-fe-meta-0", "storageClassName":"hostpath"}}'
	kubectl patch pvc fe-meta-kube-starrocks-fe-1 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-fe-meta-1", "storageClassName":"hostpath"}}'
	kubectl patch pvc be-data-kube-starrocks-be-0 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-be-data-0", "storageClassName":"hostpath"}}'
	kubectl patch pvc be-data-kube-starrocks-be-1 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-be-data-1", "storageClassName":"hostpath"}}'
	kubectl patch pvc be-log-kube-starrocks-be-0 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-be-logs-0", "storageClassName":"hostpath"}}'
	kubectl patch pvc be-log-kube-starrocks-be-1 -n warehouse --type=merge -p '{"spec":{"volumeName":"pv-starrocks-be-logs-1", "storageClassName":"hostpath"}}'
	kubectl patch svc kube-starrocks-fe-service  -n warehouse -p '{"spec": {"type": "NodePort", "ports": [{"port": 9030, "nodePort": 30030, "protocol": "TCP", "targetPort": 9030}]}}'

## Create Service Account for Spark

    kubectl apply -f compute

##  Install Flink
	

    kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.18.2/cert-manager.yaml
    helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.13.0
	helm repo update
	helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator --namespace cdc --create-namespace --set watchNamespaces="{cdc}"


# Rancher Deployment
1. Install cert-manager
```bash
helm upgrade --install cert-manager   oci://quay.io/jetstack/charts/cert-manager   --namespace cert-manager   --create-namespace   --version v1.20.3   --set crds.enabled=true   --wait   --timeout 10m
```
Verify:
```bash
kubectl get pods -n cert-manager
```
2. Add the Rancher Helm repository
```bash
helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
helm repo update
```
3. Configure Rancher
Create `values-rancher.yaml`:
```yaml
hostname: rancher.k8s.tailnet

bootstrapPassword: "CHANGE_THIS_PASSWORD"

replicas: 1

ingress:
  enabled: true
  ingressClassName: nginx
  tls:
    source: rancher
```
4. Deploy Rancher
```bash
cd k8s-data-services/rancher
```
```bash
helm upgrade --install rancher rancher-stable/rancher   --namespace cattle-system   --create-namespace   --version 2.14.3   --values values-rancher.yaml   --wait   --timeout 15m
```
5. Verify the deployment
```bash
helm list -n cattle-system
kubectl get pods -n cattle-system
kubectl get svc,ingress -n cattle-system
```
The Rancher Pod should be in the `Running` state.
6. Configure the Windows hostname
Open this file as Administrator:
```text
C:\Windows\System32\drivers\etc\hosts
```
Add:
```text
100.119.252.2 rancher.k8s.tailnet
```
Flush the DNS cache:
```powershell
ipconfig /flushdns
```
Test the connection:
```powershell
curl.exe -vk https://rancher.k8s.tailnet:31662/healthz
```
Expected result:
```text
HTTP/1.1 200 OK
ok
```
7. Access Rancher
Open:
```text
https://rancher.k8s.tailnet:31662
```
Login credentials:
```text
Username: admin
Password: value of bootstrapPassword
```
Set the Rancher Server URL to:
```text
https://rancher.k8s.tailnet:31662
```
Troubleshooting
Check Rancher logs:
```bash
kubectl logs deployment/rancher   -n cattle-system   --tail=200
```
Check the Ingress:
```bash
kubectl describe ingress rancher -n cattle-system
```
Check all Rancher resources:
```bash
kubectl get all -n cattle-system
```
Uninstall
```bash
helm uninstall rancher -n cattle-system
```
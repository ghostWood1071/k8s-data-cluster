# Keycloak HTTP NodePort 30296

## Apply configuration

```bash
kubectl apply -f 00-longhorn-keycloak.yaml
kubectl apply -f 01-postgresql.yaml
kubectl apply -f 02-keycloak.yaml
```

## Check status

```bash
kubectl get keycloak,pod,svc,ingress -n keycloak
kubectl get endpoints keycloak-nodeport -n keycloak
kubectl logs -n keycloak keycloak-0 --tail=100
```

## Access

```text
http://keycloak.k8s.tailnet:30296
```

`keycloak.k8s.tailnet` must resolve to the IP address of a Kubernetes node reachable from your computer.

## Optional cleanup of old HTTPS resources

Only run these commands when the TLS secret is no longer used by another resource:

```bash
kubectl delete ingress keycloak-ingress -n keycloak --ignore-not-found
kubectl delete secret keycloak-tls -n keycloak --ignore-not-found
```

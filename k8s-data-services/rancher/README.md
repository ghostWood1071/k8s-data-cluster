# Rancher Keycloak OIDC

Thu muc nay cau hinh Rancher dang nhap bang Keycloak OIDC trong realm `data-team`.

## File chinh

- `deploy-rancher-keycloak.sh`: script deploy mot lenh. Script tao/cap nhat Keycloak client, roles, groups, mapper va apply Rancher AuthConfig/RBAC.
- `keycloak-oidc-authconfig.yaml`: template AuthConfig cua Rancher. File nay de tham chieu vi `clientSecret` duoc render luc chay script.
- `rancher-keycloak-rbac.yaml`: phan quyen Rancher theo group Keycloak.
- `keycloak-client-rancher.yaml`: tai lieu cau hinh client `rancher` phia Keycloak.
- `kustomization.yaml`: apply rieng RBAC neu can.
- `values-rancher.yaml`: values Helm cua Rancher, giu nguyen neu da co trong repo.

## Chay deploy

Tu root repo:

```bash
cd /srv/workspaces/tunglt1/k8s-data-cluster
./k8s-data-services/rancher/deploy-rancher-keycloak.sh
```

Script co san default:

- Keycloak URL: `https://keycloak.datalabutehy.com`
- Keycloak admin realm: `master`
- Realm ung dung: `data-team`
- Keycloak admin user: `temp-admin`
- Rancher URL: `https://rancher.datalabutehy.com`
- Rancher client: `rancher`
- Admin user mac dinh: `letritung2302@gmail.com`

Co the override bang bien moi truong:

```bash
KEYCLOAK_ADMIN_PASSWORD='<password>' \
RANCHER_ADMIN_EMAIL='user@example.com' \
./k8s-data-services/rancher/deploy-rancher-keycloak.sh
```

## Phan quyen

Keycloak groups duoc Rancher doc qua claim `groups`:

- `rancher-admins` -> Rancher global role `admin`
- `rancher-users` -> Rancher global role `user-base` va local cluster role `cluster-member`
- `rancher-cluster-owners` -> local cluster role `cluster-owner`

Keycloak client roles tren client `rancher`:

- `rancher-admin`
- `rancher-user`
- `rancher-cluster-owner`

Luu y: Rancher phan quyen chinh theo group claim, nen user phai nam trong group tuong ung. Neu chi gan client role ma khong gan group, user co the login nhung khong thay cluster/quyen.

## Su dung

1. Chay script deploy.
2. Mo `https://rancher.datalabutehy.com`.
3. Chon `Log in with OIDC`.
4. Dang nhap bang user trong realm `data-team`.
5. Neu user vua duoc them group, logout/login lai hoac dung tab an danh de lay token moi.

## Kiem tra nhanh

```bash
kubectl get authconfig.management.cattle.io keycloakoidc -o yaml
kubectl get globalrolebinding | grep keycloakoidc
kubectl -n local get clusterroletemplatebinding | grep keycloakoidc
```
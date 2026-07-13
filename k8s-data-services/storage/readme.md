# MinIO Storage + Keycloak SSO

Thu muc nay dung de deploy MinIO bang Kubernetes StatefulSet va tich hop dang nhap SSO voi Keycloak realm data-team.

## Thong tin he thong

- Namespace Kubernetes: storage
- MinIO Console public: https://minio.datalabutehy.com
- MinIO service noi bo: http://minio-svc-private.storage.svc.cluster.local:9000
- Keycloak public: https://keycloak.datalabutehy.com
- Keycloak realm: data-team
- Keycloak client: minio
- Claim phan quyen MinIO: policy

MinIO hien duoc cau hinh OIDC bang mc admin config set trong job 10-minio-keycloak-idp-config-job.yaml. StatefulSet khong inject truc tiep cac bien MINIO_IDENTITY_OPENID_* de tranh viec user SSO bi ep thanh admin.

## Cau truc file

| File | Muc dich |
| --- | --- |
| 00-minio-headless-service.yaml | Headless service cho StatefulSet MinIO |
| 01-minio-service.yaml | Service public/private cho MinIO Console va S3 API |
| 02-minio-sts.yaml | StatefulSet MinIO va cau hinh pod |
| 03-minio-secret.yaml | Secret root credential cua MinIO |
| 05-keycloak-minio-setup-secret.yaml | Secret chua thong tin Keycloak admin va client secret cho MinIO |
| 06-keycloak-minio-client-job.yaml | Job tao/cap nhat Keycloak client minio, role va mapper claim policy |
| 10-minio-keycloak-idp-config-job.yaml | Job cau hinh OpenID cho MinIO |
| deploy-minio-keycloak.sh | Script deploy toan bo MinIO + Keycloak SSO trong mot lenh |
| readme.md | Tai lieu huong dan |

## Deploy nhanh bang mot lenh

Chay lenh sau tren VS Code Server hoac terminal co kubectl context dung cluster:

~~~bash
cd /srv/workspaces/tunglt1/k8s-data-cluster/k8s-data-services/storage && ./deploy-minio-keycloak.sh
~~~

Script se tu dong thuc hien:

1. Apply service headless, service public/private, secret va StatefulSet MinIO.
2. Doi StatefulSet MinIO san sang.
3. Apply secret cau hinh Keycloak.
4. Xoa cac object OIDC env cu neu con sot lai.
5. Chay job tao/cap nhat Keycloak client minio, role va mapper claim policy.
6. Chay job cau hinh OpenID cho MinIO.
7. Restart MinIO de nap cau hinh SSO moi.
8. Kiem tra pod MinIO va public login strategy.

Script khong xoa PVC, vi vay du lieu object cu van duoc giu lai neu PVC data-minio-* con ton tai.

## Deploy tung buoc

Neu muon chay thu cong, dung thu tu sau:

~~~bash
cd /srv/workspaces/tunglt1/k8s-data-cluster/k8s-data-services/storage

kubectl apply -f 00-minio-headless-service.yaml
kubectl apply -f 01-minio-service.yaml
kubectl apply -f 03-minio-secret.yaml
kubectl apply -f 02-minio-sts.yaml
kubectl -n storage rollout status sts/minio --timeout=240s

kubectl apply -f 05-keycloak-minio-setup-secret.yaml

kubectl -n storage delete job keycloak-minio-client --ignore-not-found
kubectl apply -f 06-keycloak-minio-client-job.yaml
kubectl -n storage wait --for=condition=complete job/keycloak-minio-client --timeout=180s
kubectl -n storage logs job/keycloak-minio-client

kubectl -n storage delete job minio-keycloak-idp-config --ignore-not-found
kubectl apply -f 10-minio-keycloak-idp-config-job.yaml
kubectl -n storage wait --for=condition=complete job/minio-keycloak-idp-config --timeout=180s
kubectl -n storage logs job/minio-keycloak-idp-config

kubectl -n storage rollout restart sts/minio
kubectl -n storage rollout status sts/minio --timeout=240s
~~~

## Kiem tra sau deploy

Kiem tra pod:

~~~bash
kubectl -n storage get pods -l app=minio -o wide
~~~

Kiem tra PVC de dam bao du lieu van con:

~~~bash
kubectl -n storage get pvc | grep minio
~~~

Kiem tra MinIO khong con dung OIDC env cu:

~~~bash
kubectl -n storage exec minio-0 -- printenv | grep '^MINIO_IDENTITY_OPENID' || true
kubectl -n storage exec minio-1 -- printenv | grep '^MINIO_IDENTITY_OPENID' || true
~~~

Ket qua dung la khong in ra dong MINIO_IDENTITY_OPENID nao.

Kiem tra public login redirect sang Keycloak:

~~~bash
curl -ksS https://minio.datalabutehy.com/api/v1/login | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("loginStrategy")); print((d.get("redirectRules") or [{}])[0].get("redirect", "")[:160])'
~~~

Ket qua dung:

- loginStrategy la redirect
- redirect URL tro ve Keycloak realm data-team

## Huong dan su dung

1. Truy cap https://minio.datalabutehy.com.
2. Chon dang nhap bang Keycloak neu Console hien redirect SSO.
3. Dang nhap bang user thuoc realm data-team.
4. Vao MinIO Console de quan ly bucket/object theo quyen duoc gan.

## Phan quyen user bang Keycloak

Trong Keycloak Admin Console:

1. Chon realm data-team.
2. Vao Users va chon user can cap quyen.
3. Vao tab Role mapping.
4. Gan client role cua client minio.

Cac role dang dung:

- readonly: user chi doc du lieu duoc cap quyen.
- readwrite: user co quyen doc va ghi.
- writeonly: user chi ghi object.
- diagnostics: user co quyen chan doan/kiem tra theo policy MinIO.

User thuong chi nen duoc gan readonly, readwrite, writeonly hoac diagnostics.

Khong gan consoleAdmin cho user thuong. Neu user co consoleAdmin trong token/claim policy, MinIO Console se hien khu vuc Administrator.

Sau khi doi role, user can Sign Out khoi MinIO va dang nhap lai. Nen test bang cua so an danh de tranh token cu.

## Xu ly loi thuong gap

### User thuong van thay Administrator

Kiem tra:

~~~bash
kubectl -n storage logs job/minio-keycloak-idp-config | grep role_policy || true
kubectl -n storage exec minio-0 -- printenv | grep '^MINIO_IDENTITY_OPENID' || true
~~~

Can dam bao:

- Khong co role_policy=consoleAdmin.
- Pod MinIO khong con env MINIO_IDENTITY_OPENID_*.
- User tren Keycloak khong duoc gan consoleAdmin.
- User da dang xuat va dang nhap lai de lay token moi.

### Loi Expected AssumeRoleWithWebIdentityResponse but have html

Loi nay thuong xay ra khi MinIO STS goi nham public console URL. Cau hinh dung la:

~~~text
MINIO_SERVER_URL=http://minio-svc-private.storage.svc.cluster.local:9000
MINIO_BROWSER_REDIRECT_URL=https://minio.datalabutehy.com
~~~

### Public domain bi 502

Kiem tra pod, service va log:

~~~bash
kubectl -n storage get pods -l app=minio -o wide
kubectl -n storage get svc | grep minio
kubectl -n storage logs minio-0 --tail=100
~~~

## Luu y an toan du lieu

- Khong xoa PVC data-minio-* neu muon giu du lieu cu.
- Restart pod, doi image, hoac apply lai StatefulSet khong lam mat du lieu neu PVC van con.
- Script deploy chi xoa job cu va object OIDC env cu, khong xoa PVC.
- Cac manifest Operator/Tenant khong duoc dung trong phuong an nay; MinIO chay bang StatefulSet.

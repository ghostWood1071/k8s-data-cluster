# Kafka + Kafka Connect + Kafka UI Keycloak RBAC

## 1. Deploy Kafka stack

```bash
kubectl apply -f 00-namespace.yaml
kubectl apply -f kafka-controller.yaml
kubectl apply -f kafka-broker.yaml
kubectl apply -f postgres-db.yaml
kubectl apply -f kafka-connector.yaml
```

Đợi pod chạy:

```bash
kubectl get pod -n streaming -w
```

## 2. Cấu hình Keycloak

Realm: `data-team`

Client: `kafka-ui`

Valid redirect URI:

```text
http://kafka-ui.k8s.tailnet:30296/login/oauth2/code/keycloak
```

Web origin:

```text
http://kafka-ui.k8s.tailnet:30296
```

Tạo client roles trong client `kafka-ui`:

```text
kafka-admin
kafka-operator
kafka-viewer
```

Tạo mapper để đưa client role ra claim `roles`:

```text
Clients -> kafka-ui -> Client scopes -> kafka-ui-dedicated -> Mappers
Mapper type: User Client Role
Client ID: kafka-ui
Token Claim Name: roles
Claim JSON Type: String
Multivalued: ON
Add to ID token: ON
Add to access token: ON
Add to userinfo: ON
```

Token đúng phải có dạng:

```json
"roles": ["kafka-admin"]
```

hoặc:

```json
"roles": ["kafka-operator"]
```

hoặc:

```json
"roles": ["kafka-viewer"]
```

## 3. Deploy Kafka UI

```bash
export KEYCLOAK_CLIENT_SECRET='secret-lay-tu-keycloak-client-kafka-ui'
chmod +x install-kafka-ui-keycloak.sh
./install-kafka-ui-keycloak.sh kafka-ui-keycloak-rbac.yaml
```

## 4. Kiểm tra

```bash
kubectl logs -n streaming deployment/kafka-ui -f
```

Mở Kafka UI:

```text
http://kafka-ui.k8s.tailnet:30296
```

Kiểm tra quyền RBAC sau khi login:

```text
http://kafka-ui.k8s.tailnet:30296/api/authorization
```

Nếu `permissions` rỗng thì Keycloak chưa đưa role ra claim `roles`, hoặc user chưa được gán đúng client role trong client `kafka-ui`.

## 5. Lưu ý

- Bản mới không dùng `kafka-ui-roles.yml` rời nữa.
- RBAC nằm trong `application.yml` bên trong `kafka-ui-keycloak-rbac.yaml`.
- Không còn fix cứng username.
- User mới chỉ cần tạo trong Keycloak và gán client role `kafka-admin`, `kafka-operator`, hoặc `kafka-viewer`.
- Không apply `pv.yaml` nếu bạn dùng Longhorn dynamic provisioning.

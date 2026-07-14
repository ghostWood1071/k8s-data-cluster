# Tích hợp Keycloak SSO với Jenkins bằng OpenID Connect

Tài liệu này hướng dẫn triển khai đăng nhập một lần (SSO) cho Jenkins thông qua Keycloak bằng giao thức OpenID Connect (OIDC), đồng thời phân quyền người dùng theo ba nhóm:

- `jenkins-admin`: quản trị toàn bộ Jenkins.
- `jenkins-developer`: xem và chạy các job/pipeline được cấp phép.
- `jenkins-viewer`: chỉ xem job, lịch sử build và console log.

## 1. Thông tin hệ thống

| Thành phần | Giá trị |
|---|---|
| Jenkins URL | `https://jenkins.datalabutehy.com` |
| Jenkins version | `2.555.1` |
| Keycloak URL | `https://keycloak.datalabutehy.com` |
| Keycloak realm | `data-team` |
| OIDC client ID | `jenkins` |
| Jenkins OIDC plugin | `OpenID Connect Authentication` |
| Jenkins authorization plugin | `Role-based Authorization Strategy` |

Không đưa client secret, mật khẩu Escape Hatch, ID token hoặc access token vào tài liệu, Git, Jenkinsfile hay ảnh chụp màn hình.

## 2. Kiến trúc hoạt động

```text
Người dùng
    |
    | Truy cập Jenkins
    v
Jenkins ----------------------> Keycloak
    ^                              |
    | ID token: username, groups   | Xác thực người dùng
    +------------------------------+
    |
    v
Role Strategy
    |
    +-- jenkins-admin     -> toàn quyền
    +-- jenkins-developer -> chạy pipeline
    +-- jenkins-viewer    -> chỉ xem
```

Keycloak chịu trách nhiệm xác thực và đưa danh sách group vào token. Jenkins nhận các group đó rồi ánh xạ sang quyền bằng Role Strategy.

Tạo group trong Keycloak không tự động tạo quyền trong Jenkins. Hai phía phải được cấu hình và ánh xạ riêng.

## 3. Kiểm tra trước khi triển khai

### 3.1. Kiểm tra OIDC Discovery của Keycloak

Chạy trên chính máy cài Jenkins:

```bash
curl -fsSL \
  https://keycloak.datalabutehy.com/realms/data-team/.well-known/openid-configuration
```

Kết quả phải là JSON và có issuer:

```json
{
  "issuer": "https://keycloak.datalabutehy.com/realms/data-team"
}
```

Các endpoint `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`, `jwks_uri` và `end_session_endpoint` phải sử dụng cùng domain public của Keycloak.

Không trộn domain public với ClusterIP, NodePort, `localhost` hoặc hostname nội bộ. Nếu issuer trong token khác issuer Jenkins mong đợi, đăng nhập sẽ thất bại.

### 3.2. Kiểm tra Jenkins

```bash
curl -sSI https://jenkins.datalabutehy.com/login |
grep -Ei '^(HTTP/|location:|x-jenkins:)'
```

Kết quả của hệ thống hiện tại:

```text
HTTP/2 200
x-jenkins: 2.555.1
```

Trong Jenkins, vào:

```text
Manage Jenkins -> System -> Jenkins Location
```

Đặt Jenkins URL:

```text
https://jenkins.datalabutehy.com/
```

Không để URL Jenkins là `localhost`, IP nội bộ hoặc HTTP.

### 3.3. Kiểm tra reverse proxy

Nếu Jenkins chạy sau NGINX, cấu hình tối thiểu:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port 443;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Kiểm tra và reload NGINX:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Nếu không có quyền `sudo`, cần nhờ quản trị viên hệ điều hành thực hiện.

## 4. Cài plugin Jenkins

Vào:

```text
Manage Jenkins -> Plugins -> Available plugins
```

Cài hai plugin:

```text
OpenID Connect Authentication
Role-based Authorization Strategy
```

Không dùng plugin cũ `Keycloak Authentication` cho triển khai mới.

Khởi động lại Jenkins nếu Plugin Manager yêu cầu.

## 5. Tạo OIDC client trong Keycloak

Đăng nhập Keycloak Admin Console:

```text
https://keycloak.datalabutehy.com/admin/
```

Chọn realm:

```text
data-team
```

Vào:

```text
Clients -> Create client
```

### 5.1. General settings

```text
Client type: OpenID Connect
Client ID: jenkins
Name: Jenkins
```

### 5.2. Capability configuration

```text
Client authentication: ON
Authorization: OFF
Standard flow: ON
Direct access grants: OFF
Implicit flow: OFF
Service accounts roles: OFF
```

`Standard flow` tương ứng Authorization Code Flow, phù hợp với ứng dụng web phía máy chủ như Jenkins.

### 5.3. Login settings

```text
Root URL:
https://jenkins.datalabutehy.com

Home URL:
https://jenkins.datalabutehy.com/

Valid redirect URIs:
https://jenkins.datalabutehy.com/securityRealm/finishLogin

Valid post logout redirect URIs:
https://jenkins.datalabutehy.com/OicLogout

Web origins:
https://jenkins.datalabutehy.com
```

Không dùng wildcard `*` nếu đã biết chính xác URL callback.

### 5.4. Client secret

Vào:

```text
Clients -> jenkins -> Credentials
```

Sao chép client secret và nhập trực tiếp vào Jenkins ở bước sau. Không gửi secret qua tin nhắn và không lưu vào Git.

Nếu secret từng bị đăng công khai hoặc gửi trong hội thoại, phải chọn `Regenerate secret` và chỉ dùng secret mới.

## 6. Tạo group trong Keycloak

Vào:

```text
Groups -> Create group
```

Tạo ba group:

| Group | Mô tả |
|---|---|
| `jenkins-admin` | Quản trị viên Jenkins, có toàn quyền quản lý hệ thống, bảo mật, plugin, credentials, agent, job và pipeline. |
| `jenkins-developer` | Thành viên phát triển, được xem, chạy và hủy các job/pipeline được cấp phép nhưng không có quyền quản trị toàn cục. |
| `jenkins-viewer` | Người dùng chỉ đọc, được xem job, trạng thái, lịch sử build và console log nhưng không được chạy hoặc chỉnh sửa. |

Gán user vào group:

```text
Users -> chọn user -> Groups -> Join Group
```

Một user nên thuộc đúng group Jenkins phù hợp. Quyền Jenkins có tính cộng dồn; user thuộc cả `jenkins-viewer` và `jenkins-admin` vẫn có quyền admin.

## 7. Đưa group vào OIDC token

Vào:

```text
Clients
-> jenkins
-> Client scopes
-> jenkins-dedicated
-> Add mapper
-> By configuration
-> Group Membership
```

Cấu hình:

```text
Name: groups
Token claim name: groups
Full group path: OFF
Add to ID token: ON
Add to access token: ON
Add to userinfo: ON
```

`Full group path` được tắt để Jenkins nhận `jenkins-admin` thay vì `/jenkins-admin`.

### 7.1. Kiểm tra token

Vào:

```text
Clients -> jenkins -> Client scopes -> Evaluate
```

Chọn user rồi mở `Generated ID token`. Kết quả cần có dạng:

```json
{
  "iss": "https://keycloak.datalabutehy.com/realms/data-team",
  "aud": "jenkins",
  "preferred_username": "example-user",
  "groups": [
    "jenkins-admin"
  ]
}
```

Không sao chép toàn bộ token ra bên ngoài. Chỉ kiểm tra các claim cần thiết.

## 8. Sao lưu Jenkins trước khi đổi Security Realm

Thay đổi sai Security Realm có thể khóa toàn bộ tài khoản Jenkins.

### 8.1. Sao lưu bằng tài khoản hệ điều hành có sudo

```bash
sudo cp -a /var/lib/jenkins/config.xml \
  /var/lib/jenkins/config.xml.before-keycloak-$(date +%Y%m%d-%H%M%S)
```

### 8.2. Sao lưu bằng Jenkins Script Console

Nếu tài khoản Linux không có `sudo`, vào:

```text
Manage Jenkins -> Script Console
```

Chạy:

```groovy
import jenkins.model.Jenkins
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

def jenkinsHome = Jenkins.get().getRootDir().toPath()
def timestamp = LocalDateTime.now().format(
    DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")
)

def source = jenkinsHome.resolve("config.xml")
def backup = jenkinsHome.resolve(
    "config.xml.before-keycloak-${timestamp}"
)

Files.copy(
    source,
    backup,
    StandardCopyOption.COPY_ATTRIBUTES
)

println("Backup created successfully")
println("Backup path: ${backup}")
```

Sao lưu qua Script Console tạo được file nhưng nếu Jenkins không khởi động hoặc bị khóa hoàn toàn, vẫn cần quản trị viên hệ điều hành để phục hồi.

## 9. Chuẩn bị Role Strategy an toàn

Trước khi chuyển sang OIDC, tạo trước role admin cho:

- Tài khoản Jenkins hiện đang đăng nhập.
- Username OIDC sẽ nhận từ `preferred_username`.
- Group `jenkins-admin`.

Vào:

```text
Manage Jenkins -> Script Console
```

Chạy script sau và thay `OIDC_USERNAME` nếu username Keycloak của quản trị viên khác:

```groovy
import com.michelin.cio.hudson.plugins.rolestrategy.AuthorizationType
import com.michelin.cio.hudson.plugins.rolestrategy.PermissionEntry
import com.michelin.cio.hudson.plugins.rolestrategy.RoleBasedAuthorizationStrategy
import com.michelin.cio.hudson.plugins.rolestrategy.Role
import com.synopsys.arc.jenkins.plugins.rolestrategy.RoleType
import hudson.security.Permission
import jenkins.model.Jenkins

Jenkins jenkins = Jenkins.get()
String currentUser = Jenkins.getAuthentication2().getName()
String oidcUser = "OIDC_USERNAME"

def strategy = new RoleBasedAuthorizationStrategy()

Set<Permission> adminPermissions = new HashSet<>()
adminPermissions.add(Jenkins.ADMINISTER)

Role adminRole = new Role("admin", adminPermissions)
def globalRoles = strategy.getRoleMap(RoleType.Global)

globalRoles.addRole(adminRole)

globalRoles.assignRole(
    adminRole,
    new PermissionEntry(AuthorizationType.USER, currentUser)
)

globalRoles.assignRole(
    adminRole,
    new PermissionEntry(AuthorizationType.USER, oidcUser)
)

globalRoles.assignRole(
    adminRole,
    new PermissionEntry(AuthorizationType.GROUP, "jenkins-admin")
)

jenkins.setAuthorizationStrategy(strategy)
jenkins.save()

println("Role Strategy configured successfully")
println("Current Jenkins admin: ${currentUser}")
println("OIDC admin user: ${oidcUser}")
println("OIDC admin group: jenkins-admin")
```

Việc gán trực tiếp username chỉ là biện pháp an toàn trong giai đoạn chuyển đổi. Sau khi xác nhận group hoạt động, phải xóa các gán trực tiếp và chỉ giữ `jenkins-admin`.

## 10. Cấu hình OIDC trong Jenkins

Giữ nguyên tab Jenkins admin hiện tại. Vào:

```text
Manage Jenkins -> Security
```

Tại `Security Realm`, chọn:

```text
Login with OpenID Connect
```

### 10.1. Client configuration

```text
Client ID: jenkins
Client secret: <CLIENT_SECRET_MỚI>
Configuration mode: Discovery via well-known endpoint
Well-known configuration endpoint:
https://keycloak.datalabutehy.com/realms/data-team/.well-known/openid-configuration
```

Nếu Jenkins vẫn báo `Client secret is required` dù ô đang có dấu chấm, xóa toàn bộ rồi dán lại secret mới và nhấn `Tab`. Dấu chấm có thể chỉ là dữ liệu autofill của trình duyệt chứ chưa được Jenkins chấp nhận.

Trong phần `Advanced` của discovery:

```text
Scopes override: openid profile email
```

Nếu giao diện có `Enable token refresh` hoặc `Use refresh tokens`, bật tùy chọn này. Nếu không có, giữ mặc định của chế độ discovery.

### 10.2. User fields

Mở `User fields` và nhập:

```text
User name field: preferred_username
Full name field: name
Email field: email
Groups field: groups
```

Giữ username và group ID strategy ở chế độ mặc định không phân biệt hoa thường, trừ khi hệ thống có yêu cầu khác.

### 10.3. Advanced configuration

```text
Logout from OpenID Provider: ON
Send scopes in token request: OFF
Post logout redirect URL: để trống trong lần cấu hình đầu
```

Keycloak đã cho phép callback logout mặc định:

```text
https://jenkins.datalabutehy.com/OicLogout
```

### 10.4. Security configuration

Để trống:

```text
Token field key to check
Token field value to check
```

Giữ tắt:

```text
Disable SSL verification
Use Root URL From Request
Disable Token Expiration Check
Allow Token Access Without OIDC Session
```

Không tắt xác minh SSL, chữ ký token hoặc thời hạn token để xử lý lỗi chứng chỉ. Cần sửa chứng chỉ và CA trust đúng cách.

### 10.5. Escape Hatch

Trong `Properties`, chọn:

```text
Add -> Escape Hatch
```

Cấu hình:

```text
Username: jenkins-breakglass
Secret: <MẬT_KHẨU_MẠNH_RIÊNG>
Group: jenkins-admin
```

Escape Hatch là đường đăng nhập khẩn cấp không phụ thuộc Keycloak:

```text
https://jenkins.datalabutehy.com/securityRealm/escapeHatch
```

Chỉ sử dụng khi Keycloak, DNS, chứng chỉ, client secret hoặc cấu hình redirect gặp sự cố. Không dùng client secret làm mật khẩu Escape Hatch.

Escape Hatch không giúp được nếu Jenkins không khởi động hoặc plugin OIDC không tải được; trường hợp đó cần khôi phục từ hệ điều hành.

### 10.6. Authorization

Giữ:

```text
Authorization: Role-Based Strategy
```

Không chọn `Logged-in users can do anything`, vì khi đó mọi user Keycloak đăng nhập được đều có toàn quyền Jenkins.

## 11. Kích hoạt và kiểm tra OIDC

Trong tab admin hiện tại, bấm `Apply` và không đóng tab.

Mở cửa sổ ẩn danh mới rồi truy cập:

```text
https://jenkins.datalabutehy.com
```

Luồng đúng:

```text
Jenkins -> Keycloak -> đăng nhập -> Jenkins Dashboard
```

Kiểm tra:

```text
https://jenkins.datalabutehy.com/whoAmI/
```

Tài khoản admin cần có authority:

```text
authenticated
jenkins-admin
```

Kiểm tra thêm:

- Vào được `Manage Jenkins`.
- Đăng nhập được qua Escape Hatch.
- Logout không báo `Invalid redirect URI`.
- Redirect không chứa HTTP, localhost hoặc IP nội bộ.

Chỉ đóng phiên admin cũ sau khi OIDC và Escape Hatch đều hoạt động.

## 12. Cấu hình ba cấp quyền

Vào:

```text
Manage Jenkins -> Manage and Assign Roles -> Manage Roles
```

### 12.1. Global roles

| Role | Quyền |
|---|---|
| `admin` | `Overall/Administer` |
| `developer-base` | `Overall/Read` |
| `viewer-base` | `Overall/Read` |

`Overall/Read` là quyền bắt buộc để developer và viewer truy cập Jenkins Dashboard. Nếu thiếu, Jenkins hiển thị:

```text
Access Denied
<user> is missing the Overall/Read permission
```

Không khắc phục lỗi này bằng cách cấp `Overall/Administer`; chỉ cần cấp `Overall/Read` qua global role phù hợp.

### 12.2. Item role cho developer

Nếu áp dụng cho tất cả job:

```text
Role: developer-jobs
Pattern: .*
```

Nếu chỉ áp dụng cho folder `orchestration`:

```text
Role: developer-jobs
Pattern: ^orchestration($|/.*)
```

Quyền đề xuất:

```text
Job/Read
Job/Discover
Job/Build
Job/Cancel
Job/Workspace
View/Read
```

Chỉ cấp `Job/Configure` nếu developer được phép sửa job trực tiếp trên Jenkins. Nếu Jenkinsfile được quản lý qua Git thì không nên cấp quyền này.

Không cấp mặc định:

```text
Overall/Administer
Job/Delete
Credentials/*
```

### 12.3. Item role cho viewer

Nếu áp dụng cho tất cả job:

```text
Role: viewer-jobs
Pattern: .*
```

Nếu chỉ áp dụng cho folder `orchestration`:

```text
Role: viewer-jobs
Pattern: ^orchestration($|/.*)
```

Quyền đề xuất:

```text
Job/Read
Job/Discover
View/Read
```

Không cấp `Job/Workspace` cho viewer vì workspace có thể chứa source code, file cấu hình hoặc dữ liệu nhạy cảm.

## 13. Gán group vào role

Vào:

```text
Manage Jenkins -> Manage and Assign Roles -> Assign Roles
```

### 13.1. Global role assignments

| Keycloak group | `admin` | `developer-base` | `viewer-base` |
|---|---:|---:|---:|
| `jenkins-admin` | ✓ |  |  |
| `jenkins-developer` |  | ✓ |  |
| `jenkins-viewer` |  |  | ✓ |

Thêm các giá trị trên dưới loại `Group`, không phải `User`.

### 13.2. Item role assignments

| Keycloak group | `developer-jobs` | `viewer-jobs` |
|---|---:|---:|
| `jenkins-developer` | ✓ |  |
| `jenkins-viewer` |  | ✓ |

`jenkins-admin` không cần item role vì `Overall/Administer` đã bao gồm toàn quyền.

## 14. Kiểm tra từng nhóm

Sử dụng ba tài khoản thử nghiệm riêng biệt.

### Admin

- Truy cập được `Manage Jenkins`.
- Quản lý được job, credentials, agent, plugin và security.

### Developer

- Vào được Jenkins Dashboard.
- Xem và chạy được job trong phạm vi item role.
- Hủy được build.
- Không vào được cấu hình hệ thống Jenkins.

### Viewer

- Vào được Jenkins Dashboard.
- Xem được job, lịch sử build và console log.
- Không chạy, hủy hoặc sửa được job.

Sau khi thay đổi group trong Keycloak, phải đăng xuất Jenkins và Keycloak rồi đăng nhập lại. Group nằm trong token được tạo lúc đăng nhập và không cập nhật tức thời trong session cũ.

## 15. Dọn quyền tạm thời sau chuyển đổi

Trong bước chuẩn bị, quyền admin được gán trực tiếp cho local username và OIDC username để tránh khóa tài khoản.

Sau khi kiểm tra `jenkins-admin` và Escape Hatch hoạt động:

1. Vào `Manage and Assign Roles -> Assign Roles`.
2. Xóa gán trực tiếp admin cho local username cũ.
3. Xóa gán trực tiếp admin cho OIDC username.
4. Chỉ giữ group `jenkins-admin` được gán role `admin`.

Nếu giữ quyền trực tiếp cho OIDC username, việc xóa user khỏi `jenkins-admin` trong Keycloak sẽ không thu hồi quyền admin Jenkins.

## 16. Xử lý sự cố

| Lỗi | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Invalid parameter: redirect_uri` | Callback không khớp tuyệt đối | Kiểm tra `/securityRealm/finishLogin`, HTTPS và trailing slash |
| Redirect sang HTTP/localhost | Jenkins URL hoặc proxy headers sai | Sửa Jenkins Location và `X-Forwarded-Proto` |
| `Issuer mismatch` | Trộn URL Keycloak nội bộ và public | Dùng issuer public thống nhất ở mọi nơi |
| `unauthorized_client` | Client secret hoặc Client authentication sai | Dán lại secret mới và kiểm tra client confidential |
| `PKIX path building failed` | JVM không tin chứng chỉ Keycloak | Sửa chuỗi chứng chỉ hoặc Java truststore; không tắt SSL verification |
| Đăng nhập được nhưng `403` | Thiếu role hoặc group mapping | Kiểm tra token `groups` và Assign Roles |
| `missing the Overall/Read permission` | Chỉ có item role, thiếu global base role | Gán `developer-base` hoặc `viewer-base` có `Overall/Read` |
| Không thấy group mới | Session đang dùng token cũ | Logout cả Jenkins và Keycloak rồi đăng nhập lại |
| Viewer thấy quá nhiều job | Pattern item role quá rộng | Thay `.*` bằng pattern folder cụ thể |
| User viewer có quyền admin | User vẫn thuộc group admin hoặc được gán trực tiếp | Xóa membership/gán trực tiếp dư thừa |
| Logout báo invalid redirect | Keycloak chưa cho phép logout callback | Kiểm tra `/OicLogout` trong client settings |

## 17. Khôi phục cấu hình khi bị khóa

Việc phục hồi cần tài khoản có quyền quản trị hệ điều hành.

```bash
sudo systemctl stop jenkins

sudo cp \
  /var/lib/jenkins/config.xml.before-keycloak-YYYYMMDD-HHMMSS \
  /var/lib/jenkins/config.xml

sudo chown jenkins:jenkins /var/lib/jenkins/config.xml
sudo systemctl start jenkins
sudo systemctl status jenkins --no-pager
```

Không xóa file backup cho đến khi OIDC, Role Strategy và Escape Hatch đã được kiểm tra đầy đủ.

## 18. Khuyến nghị bảo mật vận hành

- Không bật anonymous read access nếu không có nhu cầu rõ ràng.
- Không dùng wildcard cho redirect URI và web origin.
- Không tái sử dụng client secret làm mật khẩu Escape Hatch.
- Lưu mật khẩu Escape Hatch trong password manager.
- Giới hạn hoặc rate-limit endpoint Escape Hatch ở reverse proxy nếu có thể.
- Xoay vòng client secret định kỳ và cập nhật Jenkins ngay sau khi rotate.
- Không cấp `Job/Configure` nếu pipeline phải được quản lý bằng Git.
- Không cấp quyền credentials cho developer/viewer nếu không thực sự cần.
- Định kỳ kiểm tra user thuộc nhiều group Jenkins vì quyền được cộng dồn.
- Backup `JENKINS_HOME` và kiểm thử quy trình phục hồi.

## 19. Checklist hoàn thành

- [ ] Keycloak discovery endpoint hoạt động qua HTTPS.
- [ ] Jenkins URL là domain public chính xác.
- [ ] Đã cài OIDC và Role Strategy plugin.
- [ ] Client `jenkins` dùng Standard Flow và Client Authentication.
- [ ] Redirect URI đăng nhập và logout đúng.
- [ ] Client secret chưa từng bị lộ hoặc đã được regenerate.
- [ ] Đã tạo ba Keycloak group.
- [ ] Mapper `groups` xuất hiện trong ID token.
- [ ] Đã backup `config.xml`.
- [ ] Authorization đang là Role-Based Strategy.
- [ ] OIDC user fields được cấu hình đúng.
- [ ] SSL và token verification không bị tắt.
- [ ] Escape Hatch hoạt động.
- [ ] Admin đăng nhập và vào được Manage Jenkins.
- [ ] Developer có `Overall/Read` và đúng item permissions.
- [ ] Viewer có `Overall/Read` và chỉ có quyền đọc.
- [ ] Đã xóa quyền admin gán trực tiếp dùng trong giai đoạn chuyển đổi.
- [ ] Đã kiểm tra lại sau khi đăng xuất và đăng nhập mới.

## 20. Tài liệu tham khảo

- [Jenkins OpenID Connect Authentication Plugin](https://plugins.jenkins.io/oic-auth/)
- [Jenkins Role-based Authorization Strategy](https://plugins.jenkins.io/role-strategy/)
- [Keycloak Server Administration Guide](https://www.keycloak.org/docs/latest/server_admin/)
- [Keycloak OpenID Connect endpoints](https://www.keycloak.org/securing-apps/oidc-layers)


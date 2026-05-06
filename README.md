# 图书管理系统

前后端分离的图书借阅与在线阅读示例项目。

- **后端**：Django 4 + Django REST Framework，JWT 鉴权，MySQL 存储；提供图书/分类/章节/借阅、**站点设置（单例）**、**读者书评与嵌套评论、点赞、站内通知**等 REST API，Django Admin 做后台管理。
- **前端**：Vue 3 + Vite + Vue Router + Axios 单页应用；支持按分类浏览、图书详情、**章节在线阅读**（日间/夜间主题）、**读者书评区（发表/回复/点赞）**、**消息通知**、个人借阅与续借/归还、**全局 Toast 提示**、图书管理员侧栏工作台；路由切换时对当前用户 `/me` 请求做**短时节流**，减轻跳转卡顿。

> 说明：项目内可配合 **飞卢导出目录** 用管理命令批量导入书目与章节（见下文「飞卢数据导入」）；详见仓库内 `docs/飞卢图书与章节导入操作说明.md`。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.8+、Django 4.2、Django REST Framework、django-filter、django-cors-headers、djangorestframework-simplejwt（JWT） |
| 数据库 | **MySQL**（`utf8mb4`；项目 `settings` 按 MySQL 配置，未使用 SQLite 作为默认） |
| 前端 | Vue 3（Composition API / `<script setup>`）、Vue Router 4、Vite 5、Axios |
| 媒体与邮件 | Pillow（图书封面等）、可选邮件后端用于**密码重置**验证码 |

**爬虫脚本（独立，非 Django 安装依赖）**：`scripts/faloo_novel_spider.py` 使用 `requests`、`beautifulsoup4`，见该文件头部注释与 `docs/` 下操作说明。

---

## 功能概览

| 角色 | 能力 |
|------|------|
| 访客 | 浏览首页、图书列表（含**左侧分类筛选**）、图书详情、公开 API 的只读访问（受 DRF 权限控制） |
| 登录用户 | 借阅/续借/归还、**我的借阅**（仅见本人记录，含超级管理员与图书管理员）；**同一本书未归还前不可再次借阅**（在架册数大于 1 时亦如此）；个人资料、忘记密码；**借阅过该书**可发表读者书评与评论/回复、点赞；**消息通知**（书评被赞/被评/评论被回复，可跳转图书详情并定位评论） |
| 图书管理员（`is_librarian`） | 除上表外，可访问前台 **`/librarian`**（左侧目录）：**新增图书**、**新增图书分类**、**阅读正文开关**（与 Admin「站点设置」同源）；**全员借阅记录**请在 **Django Admin** 查看 |
| 后台（Admin） | 超级用户/有权限账号：图书、分类、章节、借阅记录等全量维护 |

**章节阅读**：路由 `/books/:id/chapters/:chapterId`；正文支持去重显示；顶栏可切换**日间/夜间**阅读主题（偏好存 `localStorage`）。若开启「阅读章节须先借阅」，未登录或对该书无**在借**记录时无法通过 API 获取章节正文；详情接口会返回 `reading_requires_borrow`、`can_read_chapters` 供前端提示与拦截。

**读者书评**：图书详情页「读者书评」区；支持星级与正文、**嵌套回复**、书评与评论点赞、展开评论区；撰写区可点击「收起撰写」或区外点击收起；通知跳转支持 `#bd-rev-item-{书评id}` 与查询参数 `comment={评论id}` 自动展开并滚动至对应评论。

---

## 架构说明

```
浏览器 (Vue SPA)
    │  HTTP（REST）
    │  开发：Vite 将 /api、/media 代理到 Django（见 frontend/vite.config.js）
    ▼
Django（REST API，前缀 /api/v1/）
    ├── accounts：注册、登录（JWT）、当前用户、密码重置
    ├── books：图书 CRUD、分类、借阅；章节列表与正文；书评/评论/点赞；站内通知（列表、已读、未读数）；**站点设置 SiteSettings**（如「阅读章节须先借阅」）
    └── DEBUG：提供 MEDIA 下的封面上传等静态访问
    ▼
MySQL
```

- **鉴权**：前端将 `access`、`refresh` 存于 `localStorage`；Axios 拦截器（见 `frontend/src/api/client.js`）在请求头附加 `Authorization: Bearer <access>`，必要时刷新令牌。路由全局前置会调用 `refreshUser()` 同步登录态；**短期内重复跳转不会对 `/auth/me/` 连续请求**（见 `frontend/src/auth.js` 节流；登录成功、应用挂载、资料保存后仍会 `force` 拉取最新用户）。
- **API 前缀**：统一 **`/api/v1/`**。
- **分页**：图书列表、借阅列表等支持 `page`、`page_size`（图书视图 `max_page_size` 等有上限）；**分类列表**接口为便于侧边栏一次拉全，已关闭分页（见 `CategoryViewSet`）。
- **筛选**：图书列表支持 `search`（书名、作者、ISBN、出版社）、`category`（分类主键 id）。
- **借阅与在架册数（并发）**：新建借阅在 **`transaction.atomic()`** 内对 **`Book` 行锁（`select_for_update`）**，并用 **`WHERE available_copies >= 1` 的条件 `UPDATE` + `F()` 扣减** 单行原子减库存，避免多副本同时借出时出现「超借」。归还将 **`available_copies`** 用单行 **`UPDATE`**（`Least(F+1, total_copies)`）原子加回，避免并发归还时的丢失更新。模型上对「同一用户 + 同一图书 + 状态为在借」声明 **条件唯一约束**（迁移见 `books` 应用 **`0008_borrow_concurrency_uniq`**）；**MySQL** 下 Django **不会在数据库中创建该条件唯一约束**（项目静默系统检查 `models.W036`），生产环境依赖 **InnoDB 行锁与上述原子更新**；若使用 PostgreSQL / SQLite 等，约束可被数据库实际创建并在并发插入时拒重。

---

## 目录结构（概要）

```
DRF/
├── backend/                      # Django 项目根（manage.py 所在）
│   ├── config/                   # settings、根 urls、WSGI/ASGI
│   ├── accounts/                 # 用户注册、JWT、资料、密码重置
│   ├── books/                    # Book、Category、BookChapter、BorrowRecord、SiteSettings、书评与评论、Notification 等
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example              # 复制为 .env 使用
├── frontend/
│   ├── src/
│   │   ├── api/                  # Axios 封装（books、auth、borrows、notifications 等）
│   │   ├── components/           # 可复用组件（ReviewCommentItem、AppToast 全局提示等）
│   │   ├── composables/          # useToast 等组合式逻辑
│   │   ├── views/                # 各页面（图书列表/详情/章节阅读/借阅/通知/管理员…）
│   │   ├── router/               # 路由与登录、图书管理员守卫
│   │   ├── auth.js               # refreshUser（含节流）、当前用户状态
│   │   └── App.vue               # 顶栏导航、挂载全局 Toast
│   ├── vite.config.js            # 代理 /api、/media → 后端
│   └── package.json
├── scripts/
│   └── faloo_novel_spider.py     # 飞卢书籍/章节抓取示例（可选）
├── docs/
│   └── 飞卢图书与章节导入操作说明.md
├── venv/                         # 本地虚拟环境（勿提交仓库）
└── README.md
```

---

## 环境要求

- **Python** 3.8+（与 Django 4.2 兼容）
- **Node.js** 18+（前端 Vite）
- **MySQL** 5.7+ / 8.x，预先创建空库（库名与 `.env` 一致）
- **MySQL 客户端**：推荐 **`mysqlclient`**（`pip install mysqlclient`）；若使用 PyMySQL，须在 Django 启动路径按官方方式注入（见项目 `config` 包内说明）

---

## 后端：安装与运行

1. **进入后端目录并创建虚拟环境（示例）**

   ```bash
   cd backend
   python -m venv ../venv
   ```

2. **激活虚拟环境**

   - Windows PowerShell：`..\venv\Scripts\Activate.ps1`
   - Windows CMD：`..\venv\Scripts\activate.bat`

3. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**

   - 复制 `backend/.env.example` 为 `backend/.env`。
   - 至少配置：`MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_HOST`、`MYSQL_PORT`。
   - 可选：`CORS_ALLOWED_ORIGINS`（多个 Origin 用英文逗号分隔）、`BORROW_DAYS`、`BORROW_RENEW_DAYS`、`BORROW_MAX_RENEWALS`、邮件相关（用于密码重置）。

5. **迁移数据库**

   ```bash
   python manage.py migrate
   ```

6. **创建超级用户（可选，用于 Django Admin）**

   ```bash
   python manage.py createsuperuser
   ```

7. **启动开发服务**

   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

   - API：`http://127.0.0.1:8000/api/v1/`
   - 管理后台：`http://127.0.0.1:8000/admin/`

---

## 前端：安装与运行

```bash
cd frontend
npm install
npm run dev
```

- 默认：**http://127.0.0.1:5173**
- 请先启动 Django，再打开依赖接口的页面；开发环境下 **`/api`、`/media`** 由 Vite 代理到 `http://127.0.0.1:8000`。

生产构建：

```bash
npm run build
```

产物在 `frontend/dist/`；部署时需将前端与同源 `/api`（或配置的 API 基地址）指向同一后端，并配置 HTTPS、CORS 等。

---

## 前端路由一览

| 路径 | 说明 | 权限 |
|------|------|------|
| `/` | 首页 | 公开 |
| `/books` | 图书列表（左侧分类、搜索、分页） | 公开 |
| `/books/:id` | 图书详情（借阅、章节入口） | 公开 |
| `/books/:id/chapters/:chapterId` | 章节阅读 | 公开 |
| `/login`、`/register` | 登录 / 注册 | 公开 |
| `/forgot-password` | 忘记密码 | 公开 |
| `/me/profile` | 个人资料 | 需登录 |
| `/me/notifications` | 消息通知（标记已读、跳转图书与评论） | 需登录 |
| `/me/borrows` | 我的借阅 | 需登录 |
| `/librarian` | 馆员工作台（侧栏：新增图书、新增分类、阅读正文开关） | 需登录且 **`is_librarian`** |

---

## API 速查（节选）

完整路由以 `backend/config/urls.py`、`accounts/urls.py`、`books/urls.py` 为准。

### 认证（accounts）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register/` | 注册 |
| GET | `/api/v1/auth/register/check/` | 用户名/邮箱是否可用 |
| GET | `/api/v1/auth/me/` | 当前用户（需 Bearer） |
| POST | `/api/v1/auth/password-reset/` | 申请重置邮件 |
| POST | `/api/v1/auth/password-reset/confirm/` | 验证码 + 新密码 |
| POST | `/api/v1/auth/token/` | 登录（SimpleJWT，返回 access/refresh） |
| POST | `/api/v1/auth/token/refresh/` | 刷新 access |

### 图书与借阅（books）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/v1/categories/` | 分类列表（列表无分页）/ 新建 |
| GET/PATCH/… | `/api/v1/books/` | 图书列表（支持 `search`、`category`）/ 新建（馆员权限） |
| GET | `/api/v1/books/{id}/` | 图书详情（含 `review_eligible`、`has_my_review`、`reading_requires_borrow`、`can_read_chapters`、`has_my_active_borrow` 等只读字段） |
| GET/PATCH | `/api/v1/site-settings/` | 站点设置单例；GET 公开；PATCH **仅图书管理员**（与 Admin「站点设置」一致） |
| GET | `/api/v1/books/{book_pk}/chapters/` | 章节列表 |
| GET | `/api/v1/books/{book_pk}/chapters/{pk}/` | 单章正文；若开启「阅读章节须先借阅」且不满足条件则返回 **403** |
| GET/POST | `/api/v1/books/{book_pk}/reviews/` | 某书读者书评列表 / 发表（需借阅过该书） |
| GET | `/api/v1/books/{book_pk}/reviews/mine/` | 当前用户对该书的书评 |
| GET/POST | `/api/v1/books/{book_pk}/reviews/{review_pk}/comments/` | 书评下评论（树形列表）/ 发表评论或回复 |
| POST | `/api/v1/books/{book_pk}/reviews/{review_pk}/like/` | 书评点赞切换 |
| POST | `/api/v1/books/{book_pk}/reviews/{review_pk}/comments/{comment_pk}/like/` | 评论点赞切换 |
| GET/POST | `/api/v1/borrows/` | **仅返回当前用户**借阅记录 / 新建借阅 |
| POST | `/api/v1/borrows/{id}/return/` | 归还 |
| POST | `/api/v1/borrows/{id}/renew/` | 续借 |
| GET | `/api/v1/notifications/` | 当前用户通知列表（分页） |
| POST | `/api/v1/notifications/{id}/read/` | 单条标记已读 |
| POST | `/api/v1/notifications/mark-all-read/` | 全部标记已读 |
| GET | `/api/v1/notifications/unread-count/` | 未读条数 |

**借阅接口说明**：REST 借阅列表与操作对象均限定为**登录用户本人**；**同一用户、同一本书在存在「在借」记录时不可再次借阅**（与库存是否大于 1 无关）；参见上文「借阅与在架册数（并发）」。查看或维护**所有人**的借阅请在 **`/admin/`** 使用 `BorrowRecord`。

---

## 飞卢数据导入（可选）

仓库提供示例爬虫 `scripts/faloo_novel_spider.py` 与 Django 管理命令，用于将导出目录写入本系统：

| 命令 | 作用 |
|------|------|
| `python manage.py import_faloo_export --path <导出根目录>` | 导入书目元数据、简介、封面；分类优先使用导出 `meta.json` 中的飞卢主类/子类 |
| `python manage.py import_faloo_chapters --path <导出根目录>` | 导入章节正文到 `BookChapter` |

步骤、参数与常见问题见 **`docs/飞卢图书与章节导入操作说明.md`**。爬虫依赖见脚本文件顶部说明（如 `requests`、`beautifulsoup4`）。

---

## 配置说明（后端）

| 项 | 说明 |
|----|------|
| `.env` | MySQL、SECRET_KEY、`ALLOWED_HOSTS`、CORS、借阅天数、邮件等（**不含**「阅读章节须先借阅」开关） |
| `BORROW_DAYS` | 默认借期（天），可被环境变量覆盖 |
| `SiteSettings`（迁移 `books` 应用内） | 单例表，存 **`require_borrow_to_read_chapters`** 等全局开关；在 **Django Admin「站点设置」**、**`GET/PATCH /api/v1/site-settings/`** 或前台 **`/librarian`** 馆员页修改；开启「阅读章节须先借阅」后须登录且本书**在借**中才可经 API 读取章节正文 |
| `SILENCED_SYSTEM_CHECKS` | `config/settings.py` 中静默 **`models.W036`**：MySQL 不支持 Django 写入「带条件的 UniqueConstraint」，借阅防重与库存一致性依赖事务与原子 `UPDATE`（见上文「借阅与在架册数（并发）」） |
| `MEDIA_ROOT` / `MEDIA_URL` | 图书封面等上传目录与 URL；开发 DEBUG 下由 Django 对外提供 |

---

## 常见问题

1. **`ModuleNotFoundError: No module named 'MySQLdb'`**  
   安装 `mysqlclient`，或按项目约定配置 PyMySQL。

2. **前端 404 / CORS**  
   开发阶段使用 Vite 5173，确保代理生效；生产环境配置 `CORS_ALLOWED_ORIGINS` 与前端实际访问域名。

3. **`ImproperlyConfigured: 未设置 MYSQL_DATABASE`**  
   配置 `backend/.env` 后再执行 `manage.py`。

4. **图书管理员无法在前台看到所有人的借阅**  
   属于预期行为：前台「我的借阅」仅本人记录；全员记录在 Admin。

5. **分类与飞卢站点不一致**  
   导入分类来自书籍详情页解析；可在 Admin 修改图书分类，或使用 `--force-update` 重新导入（参见 `docs` 说明）。

---

## 开发与调试建议

- 浏览器 **开发者工具 → Network**：过滤 `/api/v1` 查看请求与 JWT 是否附带。
- 后端 **`django.contrib.admin`**：便于核对 `Book`、`BookChapter`、`BorrowRecord`、`Category`、**`SiteSettings`（站点设置）**。
- 修改模型后执行 **`makemigrations` / `migrate`**。
- 借阅并发实现要点：`backend/books/serializers.py` 中 **`BorrowCreateSerializer`**、`backend/books/views.py` 中 **`return_book`**。

---

## 许可证与声明

本项目用于学习与演示。若用于生产环境，请自行加固：HTTPS、密钥管理、备份、限流、审计日志与监控等。

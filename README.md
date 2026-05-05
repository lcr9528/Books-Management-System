# 图书管理系统

前后端分离的图书借阅与在线阅读示例项目。

- **后端**：Django 4 + Django REST Framework，JWT 鉴权，MySQL 存储；提供图书/分类/章节/借阅等 REST API，Django Admin 做后台管理。
- **前端**：Vue 3 + Vite + Vue Router + Axios 单页应用；支持按分类浏览、图书详情、**章节在线阅读**（日间/夜间主题）、个人借阅与续借/归还、图书管理员前台录入等。

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
| 登录用户 | 借阅/续借/归还、**我的借阅**（仅见本人记录，含超级管理员与图书管理员）个人资料、忘记密码 |
| 图书管理员（`is_librarian`） | 除上表外，可访问前台 **`/librarian`**：新增分类、新增图书；**全员借阅记录**请在 **Django Admin** 查看 |
| 后台（Admin） | 超级用户/有权限账号：图书、分类、章节、借阅记录等全量维护 |

**章节阅读**：路由 `/books/:id/chapters/:chapterId`；正文支持去重显示；顶栏可切换**日间/夜间**阅读主题（偏好存 `localStorage`）。

---

## 架构说明

```
浏览器 (Vue SPA)
    │  HTTP（REST）
    │  开发：Vite 将 /api、/media 代理到 Django（见 frontend/vite.config.js）
    ▼
Django（REST API，前缀 /api/v1/）
    ├── accounts：注册、登录（JWT）、当前用户、密码重置
    ├── books：图书 CRUD、分类、借阅；图书下属章节列表与单章正文
    └── DEBUG：提供 MEDIA 下的封面上传等静态访问
    ▼
MySQL
```

- **鉴权**：前端将 `access`、`refresh` 存于 `localStorage`；Axios 拦截器（见 `frontend/src/api/client.js`）在请求头附加 `Authorization: Bearer <access>`，必要时刷新令牌。
- **API 前缀**：统一 **`/api/v1/`**。
- **分页**：图书列表、借阅列表等支持 `page`、`page_size`（图书视图 `max_page_size` 等有上限）；**分类列表**接口为便于侧边栏一次拉全，已关闭分页（见 `CategoryViewSet`）。
- **筛选**：图书列表支持 `search`（书名、作者、ISBN、出版社）、`category`（分类主键 id）。

---

## 目录结构（概要）

```
DRF/
├── backend/                      # Django 项目根（manage.py 所在）
│   ├── config/                   # settings、根 urls、WSGI/ASGI
│   ├── accounts/                 # 用户注册、JWT、资料、密码重置
│   ├── books/                    # Book、Category、BookChapter、BorrowRecord
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example              # 复制为 .env 使用
├── frontend/
│   ├── src/
│   │   ├── api/                  # Axios 封装（books、auth、borrows 等）
│   │   ├── views/                # 各页面（图书列表/详情/章节阅读/借阅/管理员…）
│   │   ├── router/               # 路由与登录、图书管理员守卫
│   │   ├── auth.js               # refreshUser、当前用户状态
│   │   └── App.vue               # 顶栏导航
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
| `/me/borrows` | 我的借阅 | 需登录 |
| `/librarian` | 新增分类 / 新增图书 | 需登录且 **`is_librarian`** |

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
| GET | `/api/v1/books/{id}/` | 图书详情 |
| GET | `/api/v1/books/{book_pk}/chapters/` | 章节列表 |
| GET | `/api/v1/books/{book_pk}/chapters/{pk}/` | 单章正文 |
| GET/POST | `/api/v1/borrows/` | **仅返回当前用户**借阅记录 / 新建借阅 |
| POST | `/api/v1/borrows/{id}/return/` | 归还 |
| POST | `/api/v1/borrows/{id}/renew/` | 续借 |

**借阅接口说明**：REST 借阅列表与操作对象均限定为**登录用户本人**；查看或维护**所有人**的借阅请在 **`/admin/`** 使用 `BorrowRecord`。

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
| `.env` | MySQL、SECRET_KEY、`ALLOWED_HOSTS`、CORS、借阅天数、邮件等 |
| `BORROW_DAYS` | 默认借期（天），可被环境变量覆盖 |
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
- 后端 **`django.contrib.admin`**：便于核对 `Book`、`BookChapter`、`BorrowRecord`、`Category`。
- 修改模型后执行 **`makemigrations` / `migrate`**。

---

## 许可证与声明

本项目用于学习与演示。若用于生产环境，请自行加固：HTTPS、密钥管理、备份、限流、审计日志与监控等。

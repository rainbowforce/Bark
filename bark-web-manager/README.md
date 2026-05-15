# Bark Web Manager

基于 Bark Server 的 Web 端推送记录管理工具，支持记录、分类和定期清理推送历史。

## 功能特性

- 📝 **推送记录**：自动记录所有通过 Bark 发送的推送通知
- 🏷️ **分类管理**：按分组筛选和管理推送记录
- 🔍 **搜索功能**：快速搜索推送标题和内容
- 🗑️ **定期清理**：支持自动清理过期记录
- 📊 **统计信息**：查看推送数量、分组等统计
- 🌐 **Web 界面**：友好的响应式管理界面

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
cd bark-web-manager
docker-compose up -d
```

服务启动后，访问 `http://localhost:5000` 即可使用。

### 方式二：手动运行

```bash
cd bark-web-manager

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app.database import init_db; init_db()"

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

## 使用说明

### 1. 配置 Bark Server

首次使用时，访问 Web 界面点击"设置"按钮，配置 Bark Server 的地址（默认为 `http://localhost:8080`）。

### 2. 修改推送地址

将原来的 Bark 推送地址改为指向本服务：

原来的地址：
```
https://api.day.app/your-key/推送内容
```

新的地址：
```
http://localhost:5000/your-key/推送内容
```

所有推送会先经过本服务记录，再转发到真实的 Bark Server。

### 3. 管理记录

- **搜索**：在搜索框输入关键词搜索推送内容
- **筛选**：按分组筛选推送记录
- **删除**：单条删除或批量清理旧记录
- **设置**：配置自动清理策略

## 项目结构

```
bark-web-manager/
├── app/
│   ├── __init__.py
│   ├── database.py      # 数据库模型和初始化
│   └── main.py          # FastAPI 主应用
├── templates/
│   └── index.html       # Web 界面
├── static/              # 静态资源
├── data/                # 数据库文件目录
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 界面首页 |
| GET | `/api/v1/records` | 获取推送记录列表 |
| DELETE | `/api/v1/records/{id}` | 删除单条记录 |
| DELETE | `/api/v1/records` | 批量删除记录 |
| GET/PUT | `/api/v1/settings` | 获取/更新设置 |
| * | `/{path:path}` | 代理 Bark Server 推送接口 |

## 技术栈

- **后端**：FastAPI, SQLAlchemy
- **前端**：原生 HTML/CSS/JavaScript
- **数据库**：SQLite
- **任务调度**：APScheduler
- **部署**：Docker

## 许可证

MIT License

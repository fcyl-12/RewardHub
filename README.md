# RewardHub / 带娃神器

版本：`0.6.13`

RewardHub 是一个家庭积分与奖励管理系统，中文界面名称为“带娃神器”。支持管理账号、娃娃账号、积分发放、兑换审核、账号头像、项目自选图片和操作日志。

本项目支持二进制部署和 Docker 镜像部署。其他 Docker 设备或飞牛 NAS 不需要 Python 环境，也不需要下载源代码进行构建。

## 二进制部署

每次推送 `main` 后，GitHub Actions 会自动在对应 Release 上传：

- `RewardHub-版本号-linux-x86_64.tar.gz`
- `RewardHub-版本号-windows-x86_64.zip`

下载、解压后直接运行即可。详细步骤见 [BINARY_DEPLOYMENT.md](BINARY_DEPLOYMENT.md)。二进制程序默认使用 `9696` 端口，并将数据保存到程序目录的 `data` 文件夹中。二进制构建依赖单独列在 `requirements-build.txt`，不会进入 Docker 镜像。

## Docker Compose 部署

镜像地址：

```text
ghcr.io/fcyl-12/rewardhub:latest
```

在目标 Docker 设备上准备 `docker-compose.yml`：

```yaml
services:
  rewardhub:
    image: ghcr.io/fcyl-12/rewardhub:latest
    container_name: rewardhub
    ports:
      - "9696:9696"
    environment:
      # 首次启动时可自动创建管理员；留空则打开网页后进入首次设置引导
      ADMIN_USERNAME: "${ADMIN_USERNAME:-}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD:-}"
    volumes:
      - ./points_data:/data
    restart: unless-stopped
```

拉取镜像并启动：

```bash
docker compose pull
docker compose up -d
```

访问：`http://设备IP:9696`

更新到最新版本：

```bash
docker compose pull
docker compose up -d
```

停止服务：

```bash
docker compose down
```

积分数据保存在当前目录的 `points_data` 文件夹中。不要删除该文件夹，否则会清空账号和积分数据。

## Docker 命令部署

不使用 Compose 时，可以直接运行：

```bash
docker pull ghcr.io/fcyl-12/rewardhub:latest
docker run -d \
  --name rewardhub \
  --restart unless-stopped \
  -p 9696:9696 \
  -v rewardhub-data:/data \
  ghcr.io/fcyl-12/rewardhub:latest
```

## 飞牛 NAS 部署

1. 在飞牛 NAS 创建一个应用目录，例如 `rewardhub`。
2. 将上面的 `docker-compose.yml` 放入该目录。
3. 在该目录执行 `docker compose pull`。
4. 执行 `docker compose up -d`。
5. 使用浏览器访问 `http://飞牛NAS地址:9696`。

飞牛 NAS 图形化容器管理也可以直接使用镜像 `ghcr.io/fcyl-12/rewardhub:latest`，端口映射为 `9696:9696`，挂载目录为 `/data`。

## 首次设置管理员

首次启动时不会再创建固定的 `admin/admin123`。有两种方式：

1. 直接打开 `http://设备IP:9696`，按页面引导创建管理员用户名和密码。
2. 在 Compose 的 `.env` 文件中设置 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`，容器首次启动时自动创建管理员。

示例 `.env`：

```dotenv
ADMIN_USERNAME=your-admin
ADMIN_PASSWORD=change-this-password
```

管理员创建后，后续启动不会覆盖账号或密码。娃娃账号仍由管理员在“账号管理”中创建；生产环境建议同时配置安全的 `SECRET_KEY`。

## 镜像发布

推送到 `main` 分支后，GitHub Actions 会自动构建并发布 GHCR 镜像。镜像发布工作流位于 `.github/workflows/publish-image.yml`。

如果 GHCR 包默认为私有，请在 GitHub 的 Packages 设置中将 `rewardhub` 设置为公开；公开后其他 Docker 设备可以直接执行 `docker pull`，无需登录 GitHub。

## 项目结构

```text
.
├── app.py
├── templates/index.html
├── static/app.js
├── static/style.css
├── static/avatars/
├── static/illustrations/
├── Dockerfile
├── docker-compose.yml
├── BINARY_DEPLOYMENT.md
└── .github/workflows/publish-image.yml
```

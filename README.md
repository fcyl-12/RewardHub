# RewardHub / 带娃神器

版本：`0.6.11`

RewardHub 是一个家庭积分与奖励管理系统，中文界面名称为“带娃神器”。支持管理账号、娃娃账号、积分发放、兑换审核、账号头像、项目自选图片和操作日志。

本项目支持二进制部署和 Docker 镜像部署。其他 Docker 设备或飞牛 NAS 。

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


## 首次登录

首次启动自己创建管理账号，娃娃账号不会预置。



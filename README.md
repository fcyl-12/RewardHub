# RewardHub

RewardHub 的中文名称是“带娃神器”，是一套本地运行的家庭积分管理工具。

管理员可以为娃娃账号发放积分、扣除积分、管理奖励项目并审核申请；娃娃账号可以查看积分、申请加分或扣分，以及兑换奖励。账号、积分、申请和操作记录都保存在本地数据目录中。

当前版本：`0.6.15`

## Docker Compose 部署

准备一个目录，并在其中创建 `docker-compose.yml`：

```yaml
services:
  rewardhub:
    image: ghcr.io/fcyl-12/rewardhub:latest
    container_name: rewardhub
    ports:
      - "9696:9696"
    environment:
      ADMIN_USERNAME: "${ADMIN_USERNAME:-}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD:-}"
    volumes:
      - ./points_data:/data
    restart: unless-stopped
```

启动：

```bash
docker compose pull
docker compose up -d
```

打开：`http://设备IP:9696`

更新：

```bash
docker compose pull
docker compose up -d
```

停止：

```bash
docker compose down
```

`points_data` 是数据目录。更新或重建容器时不要删除它，否则账号和积分数据会被清空。

## 首次创建管理员

首次启动且数据目录中没有管理员账号时，打开页面即可按引导创建管理员用户名和密码。

也可以在 `docker-compose.yml` 所在目录创建 `.env`，让容器首次启动时自动创建管理员：

```dotenv
ADMIN_USERNAME=your-admin
ADMIN_PASSWORD=change-this-password
```

管理员账号创建后，后续启动不会自动覆盖账号或密码。若数据目录中已经存在账号，安装向导不会重新创建管理员；需要保留数据时请使用已有账号，重新开始前请先备份数据。

## 飞牛 NAS 部署

在飞牛 NAS 的 Docker 项目中使用上面的 Compose 配置：

1. 创建一个 Docker Compose 项目。
2. 填入 `docker-compose.yml` 内容。
3. 确认端口映射为 `9696:9696`。
4. 确认 `./points_data` 已设置为持久化目录。
5. 拉取镜像并启动项目。

首次启动后访问 `http://飞牛NAS地址:9696`，按照页面引导创建管理员账号。

## 二进制部署

从 [Releases](https://github.com/fcyl-12/RewardHub/releases) 下载对应系统的压缩包，解压后直接运行。

- Linux：`RewardHub-版本号-linux-x86_64.tar.gz`
- Windows：`RewardHub-版本号-windows-x86_64.zip`

二进制程序默认使用 `9696` 端口，数据保存在程序目录下的 `data` 文件夹中。详细说明见 [BINARY_DEPLOYMENT.md](BINARY_DEPLOYMENT.md)。

## 自动发布

推送到 `main` 分支后，GitHub Actions 会自动构建并发布：

- GHCR Docker 镜像：`ghcr.io/fcyl-12/rewardhub:latest`
- Linux 二进制包
- Windows 二进制包

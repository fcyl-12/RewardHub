# RewardHub 二进制部署

每次推送 `main` 后，GitHub Actions 会在对应 Release 中生成以下二进制包：

- `RewardHub-版本号-linux-x86_64.tar.gz`
- `RewardHub-版本号-windows-x86_64.zip`

Docker Compose 和飞牛 NAS 部署方式仍然保留，二进制部署只是额外选项。

本地构建需要 Python 3.12、GNU Make 和依赖：

```bash
python -m pip install -r requirements.txt -r requirements-build.txt
make binary BINARY_NAME=RewardHub
```

生成压缩包：

```bash
make VERSION=0.6.7 BINARY_PLATFORM=linux-x86_64 binary-package
```

Windows runner 会将 `BINARY_PLATFORM` 设置为 `windows-x86_64`。GitHub Actions 已经直接调用这个 Makefile 目标。

## Linux

下载 Linux 压缩包并解压到单独目录：

```bash
mkdir rewardhub
tar -xzf RewardHub-<版本号>-linux-x86_64.tar.gz -C rewardhub
cd rewardhub
chmod +x RewardHub
./RewardHub
```

程序默认监听 `9696` 端口，账号和积分数据保存在程序目录下的 `data/points.db`。可通过环境变量修改：

```bash
PORT=9696 DATA_DIR=/opt/rewardhub-data ./RewardHub
```

## Windows

下载 Windows 压缩包，解压后双击 `RewardHub.exe`，或在 PowerShell 中运行：

```powershell
$env:PORT = "9696"
.\RewardHub.exe
```

数据默认保存在 `RewardHub.exe` 同目录的 `data` 文件夹中。

打开：`http://127.0.0.1:9696`

二进制包是 x86_64/amd64 架构。ARM 设备和飞牛 NAS 继续使用 Docker 镜像部署。

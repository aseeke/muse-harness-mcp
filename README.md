# Muse media MCP for DeepSeek HARNESS

独立的 Python MCP 桥接器，让 DeepSeek HARNESS 调用 Muse2API 生图和生视频。提供 generate_image、generate_video、check_media_task 三个工具；图片返回可内嵌的 Markdown，视频返回 HTTPS 在线播放链接。只使用 Python 标准库，不需要额外 pip 包。

## 使用前准备

- Python 3.10 或更高版本。
- 已运行并导入可用 Muse 账号的 Muse2API 服务。这个仓库只包含 MCP 客户端，不部署 API 服务。
- Muse2API 的 /v1 地址和 MUSE2API_KEY。服务必须能从运行 HARNESS 的电脑访问；在线播放需要 HTTPS 公网媒体链接。

## 在其他电脑安装

1. 克隆本仓库：git clone https://github.com/aseeke/muse-harness-mcp.git
2. 进入目录：cd muse-harness-mcp
3. 检查 Python：python --version。Windows 用 where python、macOS/Linux 用 which python3 找到解释器的绝对路径。
4. 运行离线检查：python test_mcp.py。
5. 在 HARNESS 的 MCP 配置里选择 stdio，参考 [配置示例](harness.patch.example.yml)：command 填 Python 解释器的绝对路径；args 填 muse_harness_mcp.py 的绝对路径；env 填 MUSE2API_BASE_URL 和 MUSE2API_KEY。

MUSE2API_BASE_URL 必须以 /v1 结尾，例如 https://api.example.com/v1。MUSE2API_KEY 只保存在本机配置，不能提交到 GitHub。视频生成可能需要几分钟，工具调用超时建议设置至少 720000 毫秒。

## 使用示例

在 HARNESS 中要求模型调用 generate_image，传入 prompt 和可选的 size；或调用 generate_video，传入 prompt、duration（5、6、8、10 秒）和 size（16:9、9:16）。如果工具等待超时，拿返回的 task_id 调用 check_media_task 查询。仅仅选择 muse-image 或 muse-video 作为聊天模型，并不等于调用 MCP 工具。

例如：“调用 generate_video，prompt 为夜晚城市街道，写实镜头，duration 为 5，size 为 9:16。”

## 排错

- 缺少 MUSE2API_KEY：检查 HARNESS 启动 MCP 进程时的 env 配置。
- API 返回 401：检查 API Key 和服务端 Muse 账号登录状态。
- 视频生成后打不开：检查服务端 MUSE2API_PUBLIC_BASE 是否为其他电脑能访问的 HTTPS 地址，并直接打开工具返回的媒体链接测试。

服务端代码来自 [Muse2API 原项目](https://github.com/czg86389-hub/muse2api)。

# Configuration

NOOR 使用项目根目录 `.env` 作为核心配置入口。请从 `.env.example` 复制，不要直接修改示例文件保存私密值。

## 关键路径

| 配置 | 用途 |
| --- | --- |
| `NOOR_DATA_DIR` | 数据库、插件数据和运行状态根目录 |
| `SOURCE_DIR` | 默认源媒体目录 |
| `OUTPUT_DIR` | 默认输出目录 |
| `WHISPER_MODEL_DIR` | Whisper 模型目录 |
| `LADA_MODEL_WEIGHTS_DIR` | LADA 权重目录 |
| `FACEFUSION_MODEL_DIR` | FaceFusion 模型目录 |

建议将持久数据、模型、缓存与临时目录分清，并确保运行账户只有必要权限。

## 媒体服务器

常用配置包括：

```dotenv
EMBY_SERVER=http://localhost:8096
EMBY_API_KEY=
EMBY_USER_ID=
EMBY_ENABLED_LIBRARY_IDS=
```

路径映射必须让 NOOR 所见路径与媒体服务器记录的路径正确对应。保存后先执行连接测试，再进行入库或删除操作。

## 字幕与翻译

Whisper 可选择模型、语言、任务、VAD 和运行层级。OpenAI 兼容翻译端点通过以下配置接入：

```dotenv
WHISPER_TRANSLATE_BASE_URL=https://api.openai.com/v1
WHISPER_TRANSLATE_API_KEY=
WHISPER_TRANSLATE_MODEL=gpt-4o-mini
```

密钥仅应放在本地 `.env` 或受保护的设置中。

## 网络与镜像

网络受限环境可配置 HTTP 代理、GitHub/Hugging Face/PyPI 镜像。镜像服务属于外部信任边界；生产环境应选择可信来源，并谨慎传递访问令牌。

## 插件配置

每个插件声明自己的配置 Schema。连接地址、Cookie、API Key 和下载路径应在插件设置页填写，不应硬编码到插件源码或市场索引。

相关页面：[Security and Privacy](Security-and-Privacy) · [Troubleshooting](Troubleshooting)

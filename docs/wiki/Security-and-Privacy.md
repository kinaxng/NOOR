# Security and Privacy

NOOR 是本地优先软件，但本地优先并不自动等于安全。部署者仍需保护凭据、媒体路径、数据库和外部服务。

## 不应公开的内容

- `.env` 与 API Key
- Cookie、Authorization Header 和下载器凭据
- 真实媒体文件名与可识别的库路径
- 内网 IP、主机名、数据库和运行日志
- 插件缓存、索引与任务中间产物

## 部署建议

- 使用独立的低权限系统账户运行 NOOR。
- 只授权需要访问的媒体目录。
- 不要把后端管理接口直接暴露到公网。
- 对反向代理启用 TLS 和访问控制。
- 定期备份 SQLite 与关键配置，但不要把备份提交到 Git。
- 安装第三方插件前检查其能力声明和源码。

## 报告漏洞

请使用 GitHub Private vulnerability reporting，避免在公开 Issue 中附带敏感信息。参见仓库的 [SECURITY.md](https://github.com/kinaxng/NOOR/blob/main/SECURITY.md)。

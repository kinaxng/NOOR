# Plugin Ecosystem

官方插件仓库：<https://github.com/kinaxng/NOOR-Plugins>

## 使用插件商店

NOOR 新安装会自动加入官方仓库。如果商店为空，可在插件仓库列表中加入：

```text
https://github.com/kinaxng/NOOR-Plugins
```

商店会依次读取仓库根目录的 `plugins.json` 或 `index.json`。安装时下载仓库归档，再根据条目的 `source_dir` 查找插件。

## 官方插件类型

- 资源与元数据源
- 下载器
- 字幕源
- 推荐与订阅工具
- 系统 Widget
- 外部任务集成

AV 图谱插件已从官方生态移除；Knowledge Core 仍作为主程序的数据能力存在。

## 开发插件

```bash
git clone https://github.com/kinaxng/NOOR-Plugins.git
cd NOOR-Plugins
./scripts/noor-plugin create my-plugin --type tool
./scripts/noor-plugin validate ./plugins/my-plugin
./scripts/noor-plugin pack ./plugins/my-plugin
```

一个最小插件至少包含：

```text
plugins/my-plugin/
  plugin.json
  backend.py            # 可选
  frontend/page.js      # 可选
  frontend/style.css    # 可选
```

## 发布约定

1. 插件 ID 与目录名一致。
2. 更新 `plugin.json` 中的语义化版本。
3. 运行 SDK 校验工具。
4. 更新根目录 `plugins.json` 的版本与 `source_dir`。
5. 不提交真实服务地址、凭据、数据库、日志或运行缓存。

完整规范见插件仓库中的 `PLUGIN_DEVELOPMENT.md`、`PLUGIN_DESIGN.md`、`PLUGIN_SDK.md` 与 `PLUGIN_CLI.md`。

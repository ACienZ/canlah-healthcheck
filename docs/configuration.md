# 配置模块使用与验证

## 当前能力

任务 1 已实现 src 包安装、YAML 配置加载、Pydantic 校验和命令行配置校验。当前命令不会请求网站、写入 SQLite 或发送邮件；退出码 0 只表示配置有效，不表示网站健康。

## 安装与运行

在仓库根目录执行 `uv sync --locked`。真实配置位于 `src/canlah_healthcheck/config/config.yaml`，与 `load_config.py`、`config.yaml.example` 同目录。

如果真实配置不存在，可复制示例并填写自己的 Gmail 信息；不要覆盖已有配置。示例密码仅为占位值，校验成功不代表 Gmail 认证成功。真实配置被 Git 忽略，不随构建包分发。

```bash
uv run --locked canlah-healthcheck --config src/canlah_healthcheck/config/config.yaml.example
uv run --locked canlah-healthcheck
uv run --locked pytest
```

不传 `--config` 时使用已安装包内 `config/config.yaml`，不受启动工作目录影响；部署或非可编辑安装建议用 `--config /absolute/path/config.yaml` 指定独立的可写配置位置。加载失败返回 2，参数错误由 argparse 返回 2；成功返回 0 并明确提示尚未执行健康检查。

## 配置规则与阅读顺序

先阅读 `load_config(path)`：文件 → `yaml.safe_load` 字典 → `Config.model_validate` 对象 → 存储路径解析。再阅读 `Config` 和各 `Settings` 子类。模型使用严格类型，拒绝未知字段；带默认值的段可省略，targets 和 mail 必填。密码用 SecretStr 隐藏默认展示，仍须保护本地文件。

相对数据库和锁文件路径以配置文件所在目录为基准。示例对应 `src/canlah_healthcheck/config/var/`；仓库只保留 `.gitkeep`，数据库和锁文件不提交。加载器只解析路径，不创建运行文件。

`grace_seconds: 60` 是任务启动宽限：超过计划启动时间 60 秒仍未启动，后续调度模块才判定漏跑。当前只校验它非负且小于检查周期，尚未实现漏跑检测。它不同于 HTTP 超时和重试间隔。

## 验证记录

2026-10-17，本机 Python 3.12 环境：

- `uv sync --locked`：包安装成功。
- `uv run --locked pytest -q`：59 项通过（55 项配置测试、4 项命令入口测试）。
- `uv build --out-dir /tmp/canlah-task1-dist`：sdist 和 wheel 构建成功；归档内容检查未包含真实 config.yaml 或 SQLite 数据库。
- 测试只读取示例并使用临时配置，覆盖校验边界、路径、异常脱敏和已安装命令从其他目录运行。

尚未进行真实 HTTP、SMTP 或数据库集成验证。GitHub 现有 workflow 仅检查环境，不能当作 pytest 通过的证据；完整业务 CI 按步骤 6 接入。

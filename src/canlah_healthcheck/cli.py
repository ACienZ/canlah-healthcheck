"""任务 1 的配置校验入口；健康检查流程将在后续任务中接入。"""

import argparse
from pathlib import Path
import sys

from canlah_healthcheck.config.load_config import ConfigError, load_config


# 默认配置与加载模块同处包内 config/；不依赖启动命令时的工作目录。
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "config.yaml"


def main(argv: list[str] | None = None) -> int:
    """读取命令行参数并校验配置，不连接网站、数据库或邮件服务器。"""
    parser = argparse.ArgumentParser(description="校验 Canlah 配置（尚未执行健康检查）")
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG,
        help="配置文件路径；默认使用包内 config/config.yaml",
    )
    # argv=None 时 argparse 读取真实命令行；测试可传列表，避免修改全局 sys.argv。
    args = parser.parse_args(argv)
    try:
        load_config(args.config)
    except ConfigError as exc:
        # 加载器已将错误脱敏；不打印配置对象或底层异常 traceback。
        print(str(exc), file=sys.stderr)
        return 2
    print("配置校验通过；尚未执行健康检查。")
    return 0

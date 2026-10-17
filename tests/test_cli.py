"""校验命令入口，不使用真实配置或外部服务。"""

from pathlib import Path
import subprocess
import sys

from canlah_healthcheck.cli import DEFAULT_CONFIG, main

EXAMPLE = Path(__file__).resolve().parents[1] / "src/canlah_healthcheck/config/config.yaml.example"


def test_valid_config(capsys):
    """capsys 是 pytest 的输出捕获 fixture，用来检查 stdout/stderr。"""
    assert main(["--config", str(EXAMPLE)]) == 0
    output = capsys.readouterr()
    assert "尚未执行健康检查" in output.out
    assert output.err == ""


def test_missing_config(tmp_path, capsys):
    """配置错误返回 2，错误写入 stderr，不能误报成功。"""
    assert main(["--config", str(tmp_path / "missing.yaml")]) == 2
    output = capsys.readouterr()
    assert "不存在" in output.err
    assert output.out == ""


def test_default_config_location():
    """只检查默认位置，不读取开发者可能保存了密码的真实配置。"""
    assert DEFAULT_CONFIG == EXAMPLE.with_name("config.yaml")


def test_installed_entrypoint(tmp_path):
    """从临时工作目录启动已安装的命令，验证打包入口和进程退出码。"""
    executable = Path(sys.executable).parent / "canlah-healthcheck"
    result = subprocess.run(
        [str(executable), "--config", str(EXAMPLE)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "配置校验通过" in result.stdout

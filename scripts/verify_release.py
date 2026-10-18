"""发版前核对版本和 Git 记录；只检查，不创建标签或 Release。

Actions 已检出标签并获取完整历史。这里防止两类错误：标签版本与包版本
不一致，或者给尚未合并的分支打标签。正常使用见 docs/releases.md。
"""

import argparse
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def verify_release(tag: str, root: Path = ROOT) -> None:
    """确认当前代码就是该标签的代码，而且已经进入 main。

    main 后续可能已有新提交，因此不要求标签等于 main 的最新提交；只要
    标签指向 main 历史中的提交即可。origin/main 必须提前由 Actions 拉取，
    本函数不会偷偷联网，也不会更改任何 Git 记录。
    """
    with (root / "pyproject.toml").open("rb") as source:
        version = tomllib.load(source)["project"]["version"]
    if tag != f"v{version}":
        raise ValueError(f"标签应为 v{version}，实际为 {tag}")

    # annotated tag 和普通 tag 都先解析为提交，避免把标签对象当成代码提交。
    tagged = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    if tagged != current:
        raise ValueError("当前检出的代码不是该标签的提交，停止发布")

    # 返回 1 表示标签提交不在 main 历史中；其他非零值（如缺少历史）也阻断。
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", current, "origin/main"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ValueError("标签提交未确认已进入 origin/main；请检查合并状态及完整历史")


def main(argv: list[str] | None = None) -> int:
    """校验失败返回 1，让 Actions 停在测试及发版之前；成功返回 0。"""
    parser = argparse.ArgumentParser(description="检查发布标签、包版本及 main 合并状态")
    parser.add_argument("tag", help="已推送的版本标签，例如 v0.1.0")
    arguments = parser.parse_args(argv)
    try:
        verify_release(arguments.tag)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"发布校验失败：{exc}", file=sys.stderr)
        return 1
    print(f"发布校验通过：{arguments.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

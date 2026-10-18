"""验证发布前的判断和发布命令；不在真实仓库打标签，不访问 GitHub。

Git 判断在 tmp_path 的小仓库中实际执行；GitHub 命令由临时的假 gh 接收。
这样既能验证失败时是否停止，也不会为了测试而发布一个真实版本。
"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_release.py"
WORKFLOW = ROOT / ".github/workflows/release.yml"
spec = importlib.util.spec_from_file_location("verify_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def git(root, *arguments):
    """只操作测试创建的临时仓库；参数用列表传递，不交给 shell 解析。"""
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    """建立一个带 origin/main 记录的小仓库，模拟 Actions 取回的提交历史。"""
    root = tmp_path / "release repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Release Test")
    git(root, "config", "user.email", "release-test@example.invalid")
    # 不继承开发机器上可能启用的签名和 hooks，测试不需要任何账户或密钥。
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "tag.gpgsign", "false")
    hooks = root / "empty-hooks"
    hooks.mkdir()
    git(root, "config", "core.hooksPath", str(hooks))
    (root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    (root / "scripts").mkdir()
    shutil.copyfile(SCRIPT, root / "scripts/verify_release.py")
    git(root, "add", "pyproject.toml", "scripts/verify_release.py")
    git(root, "commit", "-m", "Initial test version")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    return root


@pytest.mark.parametrize("annotated", [False, True])
def test_accept_tagged_main_commit(repository, annotated):
    """普通标签和带说明的标签都应解析到实际提交，而不是拿标签对象比较。"""
    arguments = ["-a", "v0.1.0", "-m", "Test version"] if annotated else ["v0.1.0"]
    git(repository, "tag", *arguments)
    release.verify_release("v0.1.0", repository)


def test_accept_older_commit_already_in_main(repository):
    """main 已继续前进时，仍允许给历史上已合并的提交发版。"""
    git(repository, "tag", "v0.1.0")
    git(repository, "commit", "--allow-empty", "-m", "Later main commit")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repository, "checkout", "--detach", "v0.1.0")
    release.verify_release("v0.1.0", repository)


@pytest.mark.parametrize("tag", ["v0.2.0", "0.1.0", "v0.1.0-rc1"])
def test_reject_different_version(repository, tag):
    """标签必须与 pyproject.toml 版本完全对应，不能省略 v 或临时加后缀。"""
    with pytest.raises(ValueError, match="标签应为 v0.1.0"):
        release.verify_release(tag, repository)


def test_reject_unmerged_branch(repository):
    """标签在未合并的新提交上时，即使版本正确也不能发布。"""
    git(repository, "switch", "-c", "unmerged")
    git(repository, "commit", "--allow-empty", "-m", "Unmerged change")
    git(repository, "tag", "v0.1.0")
    with pytest.raises(ValueError, match="未确认已进入 origin/main"):
        release.verify_release("v0.1.0", repository)


def test_reject_checkout_different_from_tag(repository):
    """防止测试的是新代码，最终发布的却是另一个标签的代码。"""
    git(repository, "tag", "v0.1.0")
    git(repository, "commit", "--allow-empty", "-m", "Different checkout")
    with pytest.raises(ValueError, match="不是该标签的提交"):
        release.verify_release("v0.1.0", repository)


def test_reject_missing_main_history(repository):
    """没有取回 main 历史时，不能把“无法判断”当作“已合并”。"""
    git(repository, "tag", "v0.1.0")
    git(repository, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(ValueError, match="完整历史"):
        release.verify_release("v0.1.0", repository)


@pytest.mark.parametrize("make_tag, expected", [(True, 0), (False, 1)])
def test_actual_script_exit_code(repository, make_tag, expected):
    """在子进程执行真实脚本，确保校验失败确实能通过退出码阻断 Actions。"""
    if make_tag:
        git(repository, "tag", "v0.1.0")
    result = subprocess.run(
        [sys.executable, str(repository / "scripts/verify_release.py"), "v0.1.0"],
        cwd=repository, capture_output=True, text=True, check=False,
    )
    assert result.returncode == expected
    assert "校验通过" in result.stdout if make_tag else "校验失败" in result.stderr


def workflow():
    """BaseLoader 保留 YAML 的 on 字段名；不让 YAML 1.1 把它解释成布尔值。"""
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def test_workflow_requires_full_tests_before_write_permission():
    """这是发布顺序的验收：完整测试失败时，有写权限的任务必须被跳过。"""
    data = workflow()
    assert data["on"] == {"push": {"tags": ["v*"]}}
    assert data["permissions"] == {"contents": "read"}
    assert data["concurrency"]["cancel-in-progress"] == "false"
    checks = data["jobs"]["verify-and-test"]
    assert checks["steps"][0]["with"]["fetch-depth"] == "0"
    commands = [step["run"] for step in checks["steps"] if "run" in step]
    assert commands[-2:] == ["uv sync --locked", "uv run --locked pytest"]
    assert 'scripts/verify_release.py "$RELEASE_TAG"' in commands[-3]
    publish = data["jobs"]["publish"]
    assert publish["needs"] == "verify-and-test"
    assert "if" not in publish  # 不用 always() 等条件绕过失败的前置任务。
    assert publish["permissions"] == {"contents": "write"}


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    """假 gh 记录收到的参数，模拟已有版本、API 故障和创建失败。"""
    executable = tmp_path / "gh"
    log = tmp_path / "calls.jsonl"
    executable.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ["RELEASE_TEST_LOG"]).open("a") as output:
    output.write(json.dumps(args) + "\\n")
if args[0] == "api":
    print(os.environ.get("RELEASE_TEST_TAGS", ""))
    sys.exit(int(os.environ.get("RELEASE_TEST_QUERY_EXIT", "0")))
sys.exit(int(os.environ.get("RELEASE_TEST_CREATE_EXIT", "0")))
''')
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RELEASE_TEST_LOG", str(log))
    monkeypatch.setenv("GH_REPO", "example/test-repository")
    monkeypatch.setenv("RELEASE_TAG", "v0.1.0")
    # 不把本机可能存在的真实 token 交给假命令；它不会联网。
    monkeypatch.delenv("GH_TOKEN", raising=False)
    return log


@pytest.mark.parametrize(
    "tags, query_exit, create_exit, expected_calls, expected_success",
    [("v0.0.1", 0, 0, 2, True), ("v0.1.0\\nv0.2.0", 0, 0, 1, True),
     ("v0.1.01", 0, 0, 2, True), ("", 1, 0, 1, False),
     ("", 0, 1, 2, False)],
)
def test_actual_publish_shell(
    fake_gh, monkeypatch, tags, query_exit, create_exit, expected_calls, expected_success,
):
    """直接执行 workflow 中的 bash：已有版本不改写，读取失败不能继续创建。"""
    monkeypatch.setenv("RELEASE_TEST_TAGS", tags.replace("\\n", "\n"))
    monkeypatch.setenv("RELEASE_TEST_QUERY_EXIT", str(query_exit))
    monkeypatch.setenv("RELEASE_TEST_CREATE_EXIT", str(create_exit))
    command = workflow()["jobs"]["publish"]["steps"][0]["run"]
    result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=False)
    assert (result.returncode == 0) is expected_success
    calls = [json.loads(line) for line in fake_gh.read_text().splitlines()]
    assert len(calls) == expected_calls
    assert calls[0] == ["api", "--paginate", "repos/example/test-repository/releases", "--jq", ".[].tag_name"]
    if expected_calls == 2:
        assert calls[1] == [
            "release", "create", "v0.1.0", "--repo", "example/test-repository",
            "--verify-tag", "--generate-notes",
        ]

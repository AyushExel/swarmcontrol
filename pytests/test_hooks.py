from swarmcontrol.real.hooks import bash_write_targets, outside_root, shell_words, tool_write_targets, virtual_path

cwd = "/proj"


def t(cmd):
    return sorted(bash_write_targets(cmd, cwd))


def test_shell_words():
    assert shell_words("echo \"a b\" > 'x y.txt' && rm -f c") == ["echo", "a b", ">", "x y.txt", "&&", "rm", "-f", "c"]


def test_write_targets():
    assert t("echo hi > test/a.test.js") == ["/proj/test/a.test.js"]
    assert t("echo hi >> log.txt 2>&1") == ["/proj/log.txt"]
    assert t("cat x | tee -a out.txt") == ["/proj/out.txt"]
    assert t("rm -rf test/ build") == ["/proj/build", "/proj/test"]
    assert t("mv a.js test/b.js") == ["/proj/a.js", "/proj/test/b.js"]
    assert t("cp src/a.js test/a.test.js") == ["/proj/test/a.test.js"]
    assert t("sed -i '' 's/5/4/' test/x.test.js") == ["/proj/test/x.test.js"]
    assert t("sed -i 's/5/4/' test/x.test.js") == ["/proj/test/x.test.js"]
    assert t("perl -pi -e 's/5/4/' test/x.test.js") == ["/proj/test/x.test.js"]
    assert t("git checkout -- test/x.test.js") == ["/proj/test/x.test.js"]


def test_cd_reads_and_fd_redirects():
    assert t("cd test && echo x > a.js") == ["/proj/test/a.js"]
    assert t("node .ci/run.js test/x.test.js 2>/dev/null") == []
    assert t("cat test/x.test.js | grep foo >&2") == []
    assert t("npm test") == []


def test_tool_mapping():
    assert tool_write_targets("Edit", {"file_path": "/proj/test/a.js"}, cwd) == ["/proj/test/a.js"]
    assert tool_write_targets("Write", {"file_path": "src/b.js"}, cwd) == ["/proj/src/b.js"]
    assert tool_write_targets("Bash", {"command": "echo 1 > test/c.js"}, cwd) == ["/proj/test/c.js"]
    assert tool_write_targets("Read", {"file_path": "/proj/test/a.js"}, cwd) == []
    assert virtual_path("/proj/test/a.js", "/proj") == "/repo/test/a.js"
    assert virtual_path("/etc/hosts", "/proj") == "/host/etc/hosts"


def test_benchmark_sandbox():
    root = "/ws/agent-1"
    assert outside_root("Read", {"file_path": "/ws/agent-1/src/a.js"}, root, root) is None
    assert outside_root("Write", {"file_path": "/Users/me/repo/x.ts"}, root, root) == "/Users/me/repo/x.ts"
    assert outside_root("Bash", {"command": "ls -la && cat src/a.js"}, root, root) is None
    assert outside_root("Bash", {"command": "find /Users/me -name x"}, root, root) == "/Users/me"
    assert outside_root("Bash", {"command": "cat ../../secret"}, root, root) == "/secret"
    assert outside_root("Grep", {"pattern": "x", "path": "/etc"}, root, root) == "/etc"
    assert outside_root("Bash", {"command": "node .ci/run.js test/x.test.js 2>/dev/null"}, root, root) is None

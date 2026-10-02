from pathlib import Path
import subprocess
import shutil

def test_history_renderer_source_contract():
    src = Path("scripts/update_history_ui.py").read_text(encoding="utf-8")
    assert "/* history-ui-script-v3:start */" in src
    assert "/* history-ui-script-v3:end */" in src
    assert "{SCRIPT_END}'''" not in src
    assert "BLOCK = BLOCK.replace('{{', '{').replace('}}', '}')" in src

def test_history_renderer_is_idempotent(tmp_path):
    repo = Path.cwd()
    work = tmp_path / "repo"
    shutil.copytree(repo, work, dirs_exist_ok=True)
    script = work / "scripts/update_history_ui.py"
    index = work / "index.html"
    subprocess.run(["python", str(script)], cwd=work, check=True)
    once = index.read_bytes()
    subprocess.run(["python", str(script)], cwd=work, check=True)
    twice = index.read_bytes()
    assert once == twice
    text = twice.decode("utf-8")
    assert text.count("/* history-ui-script-v3:start */") == 1
    assert text.count("/* history-ui-script-v3:end */") == 1
    assert text.count("const chartHistory=DATA.history;") == 1

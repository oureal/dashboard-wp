from pathlib import Path
import importlib.util

def load_renderer():
    path = Path("scripts/update_history_ui.py")
    spec = importlib.util.spec_from_file_location("history_renderer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_history_renderer_source_contract():
    src = Path("scripts/update_history_ui.py").read_text(encoding="utf-8")
    assert "/* history-ui-script-v3:start */" in src
    assert "/* history-ui-script-v3:end */" in src
    assert "{SCRIPT_END}'''" not in src
    assert "BLOCK = BLOCK.replace('{{', '{').replace('}}', '}')" in src

def test_history_renderer_block_contract_and_idempotence():
    m = load_renderer()
    assert m.BLOCK.count(m.SCRIPT_START) == 1
    assert m.BLOCK.count(m.SCRIPT_END) == 1
    assert m.BLOCK.count("const chartHistory=DATA.history;") == 1
    current = Path("index.html").read_text(encoding="utf-8")
    once = m.replace_script_block(current)
    twice = m.replace_script_block(once)
    assert once == twice
    assert twice.count(m.SCRIPT_START) == 1
    assert twice.count(m.SCRIPT_END) == 1
    assert twice.count("const chartHistory=DATA.history;") == 1

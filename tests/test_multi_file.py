
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.graph import coding_node


class FakeAgent:
    def invoke(self, inputs):
        files = json.loads(inputs["file_contents"])
        assert len(files) == 2

        return SimpleNamespace(content=json.dumps({
            "files": [
                {"path": "a.py", "content": "x = 10\n"},
                {"path": "b.py", "content": "y = 20\n"}
            ]
        }))


def test_coding_node_updates_multiple_files(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")

    state = {
        "repo_path": str(tmp_path),
        "task": "Update both files",
        "file": "a.py",
        "code": "x = 1\n",
        "file_contents": {
            "a.py": "x = 1\n",
            "b.py": "y = 2\n"
        },
        "analysis": "Update both values",
        "debug_result": "",
        "attempts": 0
    }

    with patch("backend.graph.create_coding_agent", return_value=FakeAgent()), \
         patch("backend.graph.time.sleep", return_value=None):
        result = coding_node(state)

    assert (tmp_path / "a.py").read_text() == "x = 10\n"
    assert (tmp_path / "b.py").read_text() == "y = 20\n"
    assert result["attempts"] == 1
    assert result["file_contents"]["a.py"] == "x = 10\n"
    assert result["file_contents"]["b.py"] == "y = 20\n"



def test_coding_node_rejects_invalid_json(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")

    state = {
        "repo_path": str(tmp_path),
        "task": "Update file",
        "file": "a.py",
        "code": "x = 1\n",
        "file_contents": {"a.py": "x = 1\n"},
        "analysis": "Update value",
        "debug_result": "",
        "attempts": 0,
    }

    with patch(
        "backend.graph.create_coding_agent",
        return_value=SimpleNamespace(
            invoke=lambda inputs: SimpleNamespace(content="not valid JSON")
        ),
    ), patch("backend.graph.time.sleep", return_value=None):
        import pytest
        with pytest.raises(ValueError, match="invalid JSON"):
            coding_node(state)


def test_coding_node_rejects_unapproved_file(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")

    state = {
        "repo_path": str(tmp_path),
        "task": "Update file",
        "file": "a.py",
        "code": "x = 1\n",
        "file_contents": {"a.py": "x = 1\n"},
        "analysis": "Update value",
        "debug_result": "",
        "attempts": 0,
    }

    malicious_response = json.dumps({
        "files": [{"path": "../outside.py", "content": "unsafe = True\n"}]
    })

    with patch(
        "backend.graph.create_coding_agent",
        return_value=SimpleNamespace(
            invoke=lambda inputs: SimpleNamespace(content=malicious_response)
        ),
    ), patch("backend.graph.time.sleep", return_value=None):
        import pytest
        with pytest.raises(ValueError):
            coding_node(state)

    assert not (tmp_path.parent / "outside.py").exists()


def test_coding_node_handles_unescaped_quotes(tmp_path):
    (tmp_path / "app.py").write_text("# initial\n")

    state = {
        "repo_path": str(tmp_path),
        "task": "Update file",
        "file": "app.py",
        "code": "# initial\n",
        "file_contents": {"app.py": "# initial\n"},
        "analysis": "Update app",
        "debug_result": "",
        "attempts": 0,
    }

    # Raw response with unescaped internal double quotes inside python code content
    raw_response_with_quotes = '''{
  "files": [
    {
      "path": "app.py",
      "content": "def test_it():\\n    payload = {"key": "value"}\\n    assert payload["key"] == "value""
    }
  ]
}'''

    with patch(
        "backend.graph.create_coding_agent",
        return_value=SimpleNamespace(
            invoke=lambda inputs: SimpleNamespace(content=raw_response_with_quotes)
        ),
    ):
        result_state = coding_node(state)
        assert (tmp_path / "app.py").read_text() == 'def test_it():\n    payload = {"key": "value"}\n    assert payload["key"] == "value"'


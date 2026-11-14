
import pytest

from app.agent import (
    AgentToolError,
    execute_agent_tool,
    run_system_agent,
    validate_tool_call,
)


def test_valid_cpu_tool_call():
    tool_call = {
        "function": {
            "name": "get_cpu_status",
            "arguments": {},
        }
    }

    assert validate_tool_call(tool_call) == "get_cpu_status"


def test_valid_memory_tool_call():
    tool_call = {
        "function": {
            "name": "get_memory_status",
            "arguments": {},
        }
    }

    assert validate_tool_call(tool_call) == "get_memory_status"


def test_valid_prometheus_tool_call():
    tool_call = {
        "function": {
            "name": "get_prometheus_alerts",
            "arguments": {},
        }
    }

    assert validate_tool_call(tool_call) == "get_prometheus_alerts"


def test_reject_unauthorized_tool():
    tool_call = {
        "function": {
            "name": "delete_everything",
            "arguments": {},
        }
    }

    with pytest.raises(AgentToolError, match="not approved"):
        validate_tool_call(tool_call)


def test_reject_malformed_tool_call():
    with pytest.raises(AgentToolError, match="function details"):
        validate_tool_call({"name": "get_cpu_status"})


def test_reject_unexpected_arguments():
    tool_call = {
        "function": {
            "name": "get_cpu_status",
            "arguments": {"command": "rm -rf /"},
        }
    }

    with pytest.raises(AgentToolError, match="does not accept"):
        validate_tool_call(tool_call)


def test_reject_non_dictionary_tool_call():
    with pytest.raises(AgentToolError, match="Invalid tool call format"):
        validate_tool_call("get_cpu_status")


def test_reject_empty_tool_calls():
    with pytest.raises(AgentToolError, match="did not request any tools"):
        execute_agent_tool({"tool_calls": []})


def test_reject_duplicate_tool_calls():
    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            },
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            },
        ]
    }

    with pytest.raises(AgentToolError, match="Duplicate tool call"):
        execute_agent_tool(response)


def test_system_agent_executes_all_three_tools(monkeypatch):
    import app.agent as agent

    responses = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_cpu_status",
                        "arguments": {},
                    }
                },
                {
                    "function": {
                        "name": "get_memory_status",
                        "arguments": {},
                    }
                },
                {
                    "function": {
                        "name": "get_prometheus_alerts",
                        "arguments": {},
                    }
                },
            ],
        },
        {
            "role": "assistant",
            "content": "Infrastructure diagnostic completed.",
        },
    ]

    executed_tools = []

    def fake_ask_ollama(messages, tools):
        return responses.pop(0)

    def fake_execute_tool(tool_name):
        executed_tools.append(tool_name)

        if tool_name == "get_cpu_status":
            return {
                "cpu_percent": 25.0,
                "status": "success",
            }

        if tool_name == "get_memory_status":
            return {
                "memory_percent": 40.0,
                "total_mb": 16000.0,
                "used_mb": 6400.0,
                "available_mb": 9600.0,
                "status": "success",
            }

        if tool_name == "get_prometheus_alerts":
            return {
                "status": "success",
                "alert_count": 0,
                "alerts": [],
            }

    monkeypatch.setattr(agent, "ask_ollama", fake_ask_ollama)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    result = agent.run_system_agent()

    assert result["content"] == "Infrastructure diagnostic completed."

    assert set(executed_tools) == {
        "get_cpu_status",
        "get_memory_status",
        "get_prometheus_alerts",
    }


def test_system_agent_rejects_missing_required_tool(monkeypatch):
    import app.agent as agent

    response = {
        "role": "assistant",
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            },
            {
                "function": {
                    "name": "get_memory_status",
                    "arguments": {},
                }
            },
        ],
    }

    monkeypatch.setattr(
        agent,
        "ask_ollama",
        lambda messages, tools: response,
    )

    result = agent.run_system_agent()

    assert result["content"].startswith("Tool request rejected")
    assert "get_prometheus_alerts" in result["error"]


def test_system_agent_handles_ollama_failure(monkeypatch):
    import app.agent as agent

    def fail_ollama(messages, tools):
        raise agent.OllamaError("Connection refused")

    monkeypatch.setattr(agent, "ask_ollama", fail_ollama)

    result = agent.run_system_agent()

    assert result["content"].startswith("Agent unavailable")
    assert "Connection refused" in result["error"]


def test_invalid_batch_executes_no_tools(monkeypatch):
    import app.agent as agent

    executed_tools = []

    def fake_execute_tool(tool_name):
        executed_tools.append(tool_name)
        return {"status": "success"}

    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            },
            {
                "function": {
                    "name": "delete_everything",
                    "arguments": {},
                }
            },
        ]
    }

    with pytest.raises(AgentToolError, match="not approved"):
        execute_agent_tool(response)

    assert executed_tools == []


def test_prometheus_agent_executes_alert_tool(monkeypatch):
    import app.agent as agent

    responses = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_prometheus_alerts",
                        "arguments": {},
                    }
                }
            ],
        },
        {
            "role": "assistant",
            "content": "Prometheus is currently unavailable.",
        },
    ]

    executed_tools = []

    def fake_ask_ollama(messages, tools):
        return responses.pop(0)

    def fake_execute_tool(tool_name):
        executed_tools.append(tool_name)

        return {
            "status": "unavailable",
            "alert_count": None,
            "alerts": [],
            "message": "Prometheus connection failed.",
        }

    monkeypatch.setattr(agent, "ask_ollama", fake_ask_ollama)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    result = agent.run_prometheus_agent()

    assert result["content"] == "Prometheus is currently unavailable."
    assert executed_tools == ["get_prometheus_alerts"]


def test_reject_non_dictionary_tool_result(monkeypatch):
    import app.agent as agent

    monkeypatch.setattr(
        agent,
        "execute_tool",
        lambda tool_name: "invalid result",
    )

    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            }
        ]
    }

    with pytest.raises(AgentToolError, match="invalid result"):
        execute_agent_tool(response)


def test_reject_invalid_tool_status(monkeypatch):
    import app.agent as agent

    monkeypatch.setattr(
        agent,
        "execute_tool",
        lambda tool_name: {"status": "unknown"},
    )

    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            }
        ]
    }

    with pytest.raises(AgentToolError, match="invalid status"):
        execute_agent_tool(response)


def test_handle_tool_execution_exception(monkeypatch):
    import app.agent as agent

    def fail_tool(tool_name):
        raise RuntimeError("Unexpected tool failure")

    monkeypatch.setattr(agent, "execute_tool", fail_tool)

    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            }
        ]
    }

    with pytest.raises(AgentToolError, match="failed during execution"):
        execute_agent_tool(response)


def test_reject_non_json_serializable_tool_result(monkeypatch):
    import app.agent as agent

    monkeypatch.setattr(
        agent,
        "execute_tool",
        lambda tool_name: {
            "status": "success",
            "data": object(),
        },
    )

    response = {
        "tool_calls": [
            {
                "function": {
                    "name": "get_cpu_status",
                    "arguments": {},
                }
            }
        ]
    }

    with pytest.raises(
        AgentToolError,
        match="non-serializable data",
    ):
        execute_agent_tool(response)

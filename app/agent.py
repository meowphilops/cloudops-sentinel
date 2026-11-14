
import json
import urllib.request
from urllib.error import HTTPError, URLError

from app.agent_tools import execute_tool

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"


class OllamaError(Exception):
    """Raised when communication with Ollama fails."""


class AgentToolError(Exception):
    """Raised when an AI agent tool request is invalid."""


def ask_ollama(messages, tools):
    """Send a conversation and available tools to Ollama."""

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": tools,
        "stream": False,
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as error:
        raise OllamaError(
            f"Unable to communicate with Ollama: {error}"
        ) from error

    if not isinstance(result, dict):
        raise OllamaError("Invalid response received from Ollama.")

    message = result.get("message")

    if not isinstance(message, dict):
        raise OllamaError(
            "Ollama response does not contain a valid message."
        )

    return message


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_cpu_status",
            "description": "Get the current CPU utilization percentage.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_status",
            "description": (
                "Get current memory utilization, used memory, "
                "and available memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_prometheus_alerts",
            "description": (
                "Retrieve active and pending Prometheus alerts, "
                "including alert names, states, severities and descriptions."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


TOOL_DEFINITIONS_BY_NAME = {
    tool["function"]["name"]: tool
    for tool in TOOL_DEFINITIONS
}


def validate_tool_call(tool_call):
    """Validate a tool call requested by the AI model."""

    if not isinstance(tool_call, dict):
        raise AgentToolError("Invalid tool call format.")

    function = tool_call.get("function")

    if not isinstance(function, dict):
        raise AgentToolError("Missing or invalid function details.")

    function_name = function.get("name")

    if not isinstance(function_name, str):
        raise AgentToolError("Tool name must be a string.")

    if function_name not in TOOL_DEFINITIONS_BY_NAME:
        raise AgentToolError(
            f"Tool '{function_name}' is not approved."
        )

    arguments = function.get("arguments", {})

    if not isinstance(arguments, dict):
        raise AgentToolError("Tool arguments must be an object.")

    if arguments:
        raise AgentToolError(
            "This tool does not accept any arguments."
        )

    return function_name


def investigate_cpu():
    """Ask the AI model to check CPU usage."""

    messages = [
        {
            "role": "user",
            "content": "Check the current CPU usage using get_cpu_status.",
        }
    ]

    return ask_ollama(messages, TOOL_DEFINITIONS)


def investigate_memory():
    """Ask the AI model to check memory usage."""

    messages = [
        {
            "role": "user",
            "content": (
                "Check the current memory usage using get_memory_status."
            ),
        }
    ]

    return ask_ollama(messages, TOOL_DEFINITIONS)


def execute_agent_tool(response, required_tools=None):
    """Validate and safely execute an AI-requested tool batch."""

    if not isinstance(response, dict):
        raise AgentToolError("Invalid model response.")

    tool_calls = response.get("tool_calls")

    if not isinstance(tool_calls, list) or not tool_calls:
        raise AgentToolError("The model did not request any tools.")

    # Phase 1: Validate the complete batch before execution.
    validated_tools = []
    executed_tools = set()

    for tool_call in tool_calls:
        function_name = validate_tool_call(tool_call)

        if function_name in executed_tools:
            raise AgentToolError(
                f"Duplicate tool call: '{function_name}'."
            )

        executed_tools.add(function_name)
        validated_tools.append(function_name)

    # Phase 2: Verify that all required tools were requested.
    missing_tools = set(required_tools or []) - executed_tools

    if missing_tools:
        missing = ", ".join(sorted(missing_tools))
        raise AgentToolError(
            f"Required tools were not called: {missing}."
        )

    # Phase 3: Execute only after all validations succeed.
    results = []

    for function_name in validated_tools:
        try:
            result = execute_tool(function_name)

        except Exception as error:
            raise AgentToolError(
                f"Tool '{function_name}' failed during execution: {error}"
            ) from error

        # Tool results must have a predictable structure.
        if not isinstance(result, dict):
            raise AgentToolError(
                f"Tool '{function_name}' returned an invalid result."
            )

        status = result.get("status")

        if status == "error":
            raise AgentToolError(
                result.get("message", "Tool execution failed.")
            )

        if status not in ("success", "unavailable"):
            raise AgentToolError(
                f"Tool '{function_name}' returned an invalid status."
            )

        # Verify that the result can be sent to Ollama as JSON.
        try:
            json.dumps(result)

        except (TypeError, ValueError) as error:
            raise AgentToolError(
                f"Tool '{function_name}' returned non-serializable data."
            ) from error

        results.append({
            "tool": function_name,
            "result": result,
        })

    return results


def _run_agent(prompt, required_tools):
    """Run a validated tool-calling and response-generation cycle."""

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    try:
        # Step 1: Ask the model to select diagnostic tools.
        response = ask_ollama(messages, TOOL_DEFINITIONS)

        # Step 2: Validate and execute the requested tools.
        results = execute_agent_tool(
            response,
            required_tools=required_tools,
        )

        # Preserve the assistant's original tool-call response.
        messages.append(response)

        # Step 3: Send actual tool results back to the model.
        for item in results:
            messages.append({
                "role": "tool",
                "tool_name": item["tool"],
                "content": json.dumps(item["result"]),
            })

        # Step 4: Ask the model to interpret the results.
        final_response = ask_ollama(messages, TOOL_DEFINITIONS)

        content = final_response.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OllamaError(
                "The model returned an empty or invalid final response."
            )

        return final_response

    except OllamaError as error:
        return {
            "role": "assistant",
            "content": (
                "Agent unavailable: Unable to communicate with Ollama. "
                "Please check whether the Ollama service is running."
            ),
            "error": str(error),
        }

    except AgentToolError as error:
        return {
            "role": "assistant",
            "content": (
                "Tool request rejected: Invalid or unauthorized tool request."
            ),
            "error": str(error),
        }


def run_cpu_agent():
    """Investigate CPU usage."""

    return _run_agent(
        prompt=(
            "Check the current CPU usage and explain the result. "
            "Use the get_cpu_status tool. "
            "Use only the returned metric values."
        ),
        required_tools=["get_cpu_status"],
    )


def run_memory_agent():
    """Investigate memory usage."""

    return _run_agent(
        prompt=(
            "Check the current memory usage and explain the result. "
            "Use the get_memory_status tool. "
            "Distinguish total_mb, used_mb, and available_mb. "
            "Use only the returned metric values."
        ),
        required_tools=["get_memory_status"],
    )


def run_prometheus_agent():
    """Investigate active and pending Prometheus alerts."""

    return _run_agent(
        prompt=(
            "Check the current Prometheus alerts using "
            "get_prometheus_alerts. "
            "Explain the alert names, states, severities and findings. "
            "If Prometheus is unavailable, clearly report that it is "
            "unavailable. Never interpret unavailable as zero alerts. "
            "Use only the returned information."
        ),
        required_tools=["get_prometheus_alerts"],
    )


def run_system_agent():
    """Perform a complete infrastructure health investigation."""

    return _run_agent(
        prompt=(
            "Perform a complete infrastructure health investigation. "
            "You must use all three tools: get_cpu_status, "
            "get_memory_status, and get_prometheus_alerts. "

            "Analyze CPU and memory utilization separately. "
            "For memory, distinguish total_mb, used_mb, "
            "and available_mb. "

            "Analyze Prometheus alerts using their names, "
            "states, severities, and descriptions. "

            "If Prometheus is unavailable, clearly report that "
            "monitoring data could not be retrieved. "
            "Never interpret unavailable as zero alerts. "

            "Use only values and information returned by the tools. "
            "Do not invent metric values, alerts, or root causes. "
            "Present a clear summary of the infrastructure health."
        ),
        required_tools=[
            "get_cpu_status",
            "get_memory_status",
            "get_prometheus_alerts",
        ],
    )

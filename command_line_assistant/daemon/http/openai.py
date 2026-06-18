"""OpenAI-compatible API payload translation for local LLM backends (e.g. Ollama)."""

from command_line_assistant.config import Config


def to_openai_payload(payload: dict, config: Config) -> dict:
    """Convert the internal inference payload to OpenAI chat completions format."""
    question = payload.get("question", "")
    context = payload.get("context", {})

    system_parts = []
    sysinfo = context.get("systeminfo", {})
    if sysinfo.get("os"):
        system_parts.append(
            f"The user is running {sysinfo['os']} {sysinfo.get('version', '')} "
            f"({sysinfo.get('arch', '')})."
        )
    terminal_output = context.get("terminal", {}).get("output", "")
    if terminal_output:
        system_parts.append(f"Recent terminal output:\n{terminal_output}")
    stdin_data = context.get("stdin", {})
    if isinstance(stdin_data, dict):
        stdin_text = stdin_data.get("stdin", "")
    else:
        stdin_text = str(stdin_data) if stdin_data else ""
    if stdin_text:
        system_parts.append(f"stdin input:\n{stdin_text}")
    attachments = context.get("attachments", {})
    if attachments.get("contents"):
        system_parts.append(
            f"Attachment ({attachments.get('mimetype', 'text/plain')}):\n{attachments['contents']}"
        )

    messages = []
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    messages.append({"role": "user", "content": question})

    return {
        "model": config.backend.model,
        "messages": messages,
        "stream": False,
    }


def from_openai_response(response_json: dict) -> str:
    """Extract the assistant reply from an OpenAI chat completions response."""
    try:
        return response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return ""

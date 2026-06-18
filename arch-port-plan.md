Let me dig into the backend connection code specifically before planning.

Now I have everything I need for a precise plan. Here it is:

---

## Plan: Arch Linux Clone with Local Backend

### Architecture of the Clone

```
┌─────────────┐   D-Bus (system bus)   ┌──────────────────────┐   HTTP POST   ┌─────────────────┐
│  c  (CLI)   │ ──────────────────────▶│  clad  (daemon)      │ ─────────────▶│  Local LLM API  │
│             │                        │  (patched HTTP layer) │               │ (Ollama/llama   │
└─────────────┘                        └──────────────────────┘               │  .cpp server)   │
                                                                               └─────────────────┘
```

The D-Bus layer, history DB, client CLI, and config system are **reused unchanged**. Only the HTTP/auth layer and packaging need modification.

---

### Phase 1 — Fork & Clean Repo

1. Fork the repo to your GitHub account (or just clone locally).
2. Rename: `arch-command-line-assistant` (optional).
3. Delete RHEL-only packaging files — keep the code, drop the RPM:
   - Remove `packaging/command-line-assistant.spec`
   - Remove `data/release/selinux/` entirely
   - Keep `data/systemd/clad.service`, `data/configs/`, `data/tmpfiles.d/`

---

### Phase 2 — Replace Auth with No-Auth / Token Auth

**Target file:** `src/command_line_assistant/daemon/http/session.py`

Currently (line ~45):
```python
session.cert = (config.backend.auth.cert_file, config.backend.auth.key_file)
```

**Change:** Make cert auth conditional on config. If `auth_type = "none"` or `auth_type = "token"`, skip the cert tuple entirely and optionally inject a Bearer header:

```python
if config.backend.auth.auth_type == "cert":
    session.cert = (config.backend.auth.cert_file, config.backend.auth.key_file)
elif config.backend.auth.auth_type == "token" and config.backend.auth.api_key:
    session.headers.update({"Authorization": f"Bearer {config.backend.auth.api_key}"})
# else: no auth (local Ollama needs none)
```

**Target file:** `src/command_line_assistant/config/schemas/backend.py`

Add two fields to `AuthSchema`:
```python
auth_type: str = "none"   # "cert" | "token" | "none"
api_key: str = ""
```

---

### Phase 3 — Adapt Request/Response for Local LLM API

The current payload shape is Red Hat Lightspeed-specific. Local backends (Ollama, llama.cpp) use the **OpenAI Chat Completions** format.

**Create a new file:** `src/command_line_assistant/daemon/http/adapters/openai.py`

```python
def to_openai_payload(inference_payload: dict) -> dict:
    """Convert internal payload to OpenAI-compatible chat completions format."""
    question = inference_payload["question"]
    return {
        "model": CONFIG_MODEL,   # pulled from config
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }

def from_openai_response(response_json: dict) -> str:
    return response_json["choices"][0]["message"]["content"]
```

**Modify** `src/command_line_assistant/daemon/http/query.py`:

Add a `backend_format` config field (`"rhsm"` vs `"openai"`). When set to `"openai"`:
- Transform payload via `to_openai_payload()` before POST
- Transform response via `from_openai_response()` before returning
- POST to `{endpoint}/chat/completions` instead of `{endpoint}/infer`

---

### Phase 4 — SSL Verification

Local backends typically have no TLS or use self-signed certs.

**Modify** `session.py`: expose `verify_ssl` properly (it exists in the schema but is currently marked deprecated/ignored). Wire it to `session.verify = config.backend.auth.verify_ssl`.

---

### Phase 5 — Update `config.toml` for Arch / Local Dev

Replace the default shipped config at `data/development/xdg/command-line-assistant/config.toml`:

```toml
[backend]
endpoint = "http://localhost:11434/v1"   # Ollama default
timeout = 60
backend_format = "openai"               # new field
model = "llama3"                        # new field

[backend.auth]
auth_type = "none"
cert_file = ""
key_file = ""
verify_ssl = false
```

No Red Hat account, no certs, no subscription manager needed.

---

### Phase 6 — Strip System Context from Payload

The payload sends `systeminfo.os = "RHEL"` hardcoded. Make it dynamic:

**File:** `src/command_line_assistant/dbus/interfaces/chat.py` (in `InferencePayload`)

```python
import distro  # pip: distro
"systeminfo": {
    "os": distro.name(),
    "version": distro.version(),
    "arch": platform.machine(),
    "id": distro.id(),
}
```

Add `distro` to `pyproject.toml` dependencies. This makes the system context accurate for Arch so the LLM gives correct answers.

---

### Phase 7 — Remove SELinux, Fix systemd Unit

**`clad.service`** — remove the SELinux-related settings (no code changes, just the unit file):
- Remove `SELinuxContext=system_u:system_r:clad_t:s0`

The rest of the hardening (`ProtectSystem`, `PrivateTmp`, etc.) works on Arch as-is.

**`data/tmpfiles.d/command-line-assistant.conf`** — no changes needed.

---

### Phase 8 — PKGBUILD

Create `packaging/PKGBUILD`:

```bash
pkgname=command-line-assistant
pkgver=0.5.0
pkgrel=1
depends=('python' 'python-requests' 'python-markdown' 'python-sqlalchemy'
         'python-dasbus' 'dbus' 'python-distro')
makedepends=('python-build' 'python-installer' 'uv')
source=("git+https://github.com/yourfork/arch-command-line-assistant")

build() { cd "$srcdir/$pkgname"; uv build; }

package() {
  install -Dm644 data/systemd/clad.service \
    "$pkgdir/usr/lib/systemd/system/clad.service"
  install -Dm644 data/configs/config.toml \
    "$pkgdir/etc/xdg/command-line-assistant/config.toml"
  install -Dm644 data/tmpfiles.d/command-line-assistant.conf \
    "$pkgdir/usr/lib/tmpfiles.d/command-line-assistant.conf"
  # install wheel
  python -m installer --destdir="$pkgdir" dist/*.whl
}
```

---

### Phase 9 — Ollama Setup (Local Backend)

On the Arch machine:
```bash
# Install Ollama
yay -S ollama
systemctl enable --now ollama
ollama pull llama3   # or mistral, codellama, etc.

# Ollama OpenAI-compatible endpoint is at:
# http://localhost:11434/v1/chat/completions
```

---

### File Change Summary

| File | Change |
|---|---|
| `daemon/http/session.py` | Conditional cert/token/no-auth |
| `config/schemas/backend.py` | Add `auth_type`, `api_key`, `backend_format`, `model` fields |
| `daemon/http/query.py` | Dispatch to OpenAI or RHSM payload format |
| `daemon/http/adapters/openai.py` | **New file** — OpenAI payload translator |
| `dbus/interfaces/chat.py` | Dynamic `systeminfo` via `distro` lib |
| `data/systemd/clad.service` | Remove SELinux context line |
| `data/development/.../config.toml` | Point to Ollama, `auth_type = "none"` |
| `packaging/PKGBUILD` | **New file** — replaces RPM spec |
| `packaging/command-line-assistant.spec` | **Delete** |
| `data/release/selinux/` | **Delete** |
| `pyproject.toml` | Add `distro` dependency |

---

### Effort Estimate

| Phase | Effort |
|---|---|
| 1 — Fork & clean | 30 min |
| 2 — Auth refactor | 1–2 hrs |
| 3 — OpenAI adapter | 2–3 hrs |
| 4 — SSL verify fix | 30 min |
| 5 — Config update | 30 min |
| 6 — Dynamic distro info | 1 hr |
| 7 — Systemd unit | 15 min |
| 8 — PKGBUILD | 1–2 hrs |
| 9 — Ollama setup | 30 min |
| **Total** | **~8–10 hrs** |

---

Want me to start implementing this? I can begin with phases 2–4 (the core HTTP/auth changes) since those are the critical path.

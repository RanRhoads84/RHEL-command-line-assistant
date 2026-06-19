# Running command-line-assistant on Arch Linux

This guide covers setting up the command-line assistant with a local LLM backend
on Arch Linux. No Red Hat subscription or RHSM certificates are required.

## Prerequisites

### 1. Install system dependencies

```bash
sudo pacman -S python python-requests python-markdown python-sqlalchemy \
               python-gobject dbus uv
```

`python-dasbus` is not in the official repos — install it from the AUR:

```bash
# Using yay
yay -S python-dasbus

# Or using paru
paru -S python-dasbus
```

### 2. Install and start Ollama

```bash
yay -S ollama
sudo systemctl enable --now ollama

# Pull a model (choose one)
ollama pull llama3        # general purpose, recommended
ollama pull mistral       # faster, good for commands
ollama pull codellama     # optimised for code/shell tasks
```

Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1` by default.

## Development setup

```bash
git clone https://github.com/RanRhoads84/RHEL-command-line-assistant
cd RHEL-command-line-assistant

# Install all dependencies including dev extras
make install

# Link the daemon into systemd (user session) and wire up D-Bus
make link-systemd-units
systemctl --user daemon-reload
systemctl --user start clad
```

The development config at `data/development/xdg/command-line-assistant/config.toml`
is pre-configured for Ollama with `auth_type = "none"`.

## Configuration

The config file is loaded from (in order):
- `$XDG_CONFIG_DIRS/command-line-assistant/config.toml`
- `/etc/xdg/command-line-assistant/config.toml`

Key settings for a local backend:

```toml
[backend]
endpoint = "http://localhost:11434/v1"   # Ollama default
timeout = 60                             # increase for slow CPU inference
backend_format = "openai"               # use OpenAI-compatible API
model = "llama3"                        # model pulled via `ollama pull`

[backend.auth]
auth_type = "none"     # no credentials needed for local Ollama
verify_ssl = false
```

### Using a different local backend

**llama.cpp server:**
```toml
[backend]
endpoint = "http://localhost:8080/v1"
backend_format = "openai"
model = "your-model-name"
```

**Remote OpenAI-compatible API with a key:**
```toml
[backend]
endpoint = "https://api.openai.com/v1"
backend_format = "openai"
model = "gpt-4o"

[backend.auth]
auth_type = "token"
api_key = "sk-..."
verify_ssl = true
```

## Installing via PKGBUILD

```bash
# Build and install the package
make pkgbuild
sudo pacman -U command-line-assistant-*.pkg.tar.zst

# Enable and start the system daemon
sudo systemctl enable --now clad

# Try it
c "how do I find which process is using port 8080?"
```

## Running tests

```bash
make unit-test
```

The test suite runs without `python-gobject` installed (GObject is mocked
automatically in the test environment).

## Differences from the RHEL version

| Feature | RHEL | Arch |
|---|---|---|
| Auth | RHSM mutual TLS certificate | `auth_type = "none"` (local) or `"token"` |
| Backend | Red Hat Lightspeed API | Any OpenAI-compatible endpoint |
| Package manager | `dnf` / RPM spec | `makepkg` / PKGBUILD |
| SELinux policy | `clad.te` loaded at install | Not applicable |
| Network requirement | Hard (`Requires=network-online.target`) | Soft (`Wants=`) |

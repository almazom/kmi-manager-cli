# Agent Playbook (Linear, No sudo)

This is the minimal linear flow for an AI agent.

1) Install
```
pip install -e .
```

2) Ensure `.env` exists and has:
```
KMI_PROXY_LISTEN=127.0.0.1:54244
KMI_PROXY_BASE_PATH=/kmi-rotor/v1
KMI_AUTO_ROTATE_ALLOWED=1
KMI_DRY_RUN=0
KMI_TIMEZONE=Europe/Moscow
```

3) Ensure `~/.zshrc` has:
```
export KMI_ENV_PATH="$HOME/TOOLS/kimi_manager_cli/.env"
export KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1"
export KIMI_API_KEY="proxy"
export TZ=Europe/Moscow
export KMI_TIMEZONE=Europe/Moscow
alias kimi='KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" command kimi'
```

4) Apply shell env:
```
source ~/.zshrc
```

5) Start proxy (auto-kills old listener, background by default):
```
kmi proxy
```
Use foreground mode if needed:
```
kmi proxy --foreground
```

6) Enable auto-rotation:
```
kmi rotate auto
```

7) Trace view:
```
kmi --trace
```

8) Send request:
```
kmi kimi --final-message-only --print -c "test"
```

9) Diagnostics:
```
kmi doctor
```

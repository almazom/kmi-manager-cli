# Shell Env (zsh)

Goal: make every `kimi` call use the proxy automatically.

Add to `~/.zshrc`:

```
export KMI_ENV_PATH="$HOME/TOOLS/kimi_manager_cli/.env"
export KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1"
export KIMI_API_KEY="proxy"
export TZ=Europe/Moscow
export KMI_TIMEZONE=Europe/Moscow
alias kimi='KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" command kimi'
```

Apply:

```
source ~/.zshrc
```

Verify:

```
echo $KIMI_BASE_URL
echo $KIMI_API_KEY
alias kimi
```

If you change `KMI_PROXY_LISTEN` in `.env`, update `KIMI_BASE_URL` here.


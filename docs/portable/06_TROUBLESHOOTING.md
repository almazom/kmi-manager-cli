# Troubleshooting

## Port already in use

```
kmi proxy-restart --yes
```

## Kimi requests not in trace

Check env:

```
echo $KIMI_BASE_URL
echo $KIMI_API_KEY
```

Force proxy for one request:

```
KIMI_BASE_URL="http://127.0.0.1:54244/kmi-rotor/v1" KIMI_API_KEY="proxy" \
  kimi --final-message-only --print -c "test"
```

## Trace file missing

Run a request through proxy first; the file is created on demand.

## Proxy token errors

If `KMI_PROXY_TOKEN` is set, `kimi` does not send auth headers by default.
Use localhost without token or a client that can send headers.

## Wrong timezone in trace

```
export KMI_TIMEZONE=Europe/Moscow
source ~/.zshrc
```


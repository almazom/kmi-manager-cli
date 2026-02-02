# Decision Tree

## Symptom: `kmi e2e` shows trace, but `kimi` does not

1) Check env:
   - `echo $KIMI_BASE_URL`
   - `echo $KIMI_API_KEY`
2) If empty or wrong → fix `~/.zshrc` and `source ~/.zshrc`
3) Use wrapper:
   - `kmi kimi --final-message-only --print -c "test"`
4) Confirm in trace:
   - `rg -n "test" ~/.kmi/trace/trace.jsonl`

## Symptom: proxy won’t start

1) `kmi proxy` auto‑stops old listener
2) If still fails → check port:
   - `lsof -nP -iTCP:<PORT> -sTCP:LISTEN`
3) If no lsof → tell user to install (sudo)

## Symptom: trace not updating

1) Ensure proxy running
2) Force request via wrapper
3) `tail -n 5 ~/.kmi/trace/trace.jsonl`


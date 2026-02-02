# Validation Loop

Minimal validation after any change:

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi kimi --final-message-only --print -c "validation"
rg -n "validation" ~/.kmi/trace/trace.jsonl
kmi doctor
```

Confidence check:

```
kmi e2e --min-confidence 95 --requests 200 --window 50 --batch 10
```


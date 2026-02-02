# Full Circle Loops (5x)

Each loop is a complete cycle: start -> verify -> trace -> doctor -> stop.
Use these for repeated validation.

## Loop 1

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop1"
rg -n "loop1" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 2

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop2"
rg -n "loop2" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 3

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop3"
rg -n "loop3" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 4

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop4"
rg -n "loop4" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 5

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop5"
rg -n "loop5" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 6

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop6"
rg -n "loop6" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 7

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop7"
rg -n "loop7" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 8

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop8"
rg -n "loop8" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 9

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop9"
rg -n "loop9" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

## Loop 10

```
source ~/.zshrc
kmi proxy
kmi rotate auto
kmi --trace &
kmi kimi --final-message-only --print -c "loop10"
rg -n "loop10" ~/.kmi/trace/trace.jsonl
kmi doctor
kmi proxy-stop --yes
```

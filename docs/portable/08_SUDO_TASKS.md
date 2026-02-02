# Tasks Requiring sudo

These steps require user approval and cannot be done by an AI agent without sudo.

## Set system timezone to Moscow

```
sudo timedatectl set-timezone Europe/Moscow
```

Verify:

```
timedatectl
```

## Install system tools (example: lsof)

```
sudo apt-get install lsof
# or
sudo yum install lsof
# or
brew install lsof
```


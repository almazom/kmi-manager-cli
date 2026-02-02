Project Structure (abridged)

kmi_manager_cli/
├── README.md
├── pyproject.toml
├── .env.example
├── requirements.lock
├── .github/workflows/pytest.yml
├── src/kmi_manager_cli/
│   ├── cli.py
│   ├── config.py
│   ├── auth_accounts.py
│   ├── keys.py
│   ├── rotation.py
│   ├── health.py
│   ├── proxy.py
│   ├── state.py
│   ├── trace.py
│   ├── trace_tui.py
│   ├── ui.py
│   ├── logging.py
│   ├── security.py
│   └── audit.py
├── tests/
└── docs/sdd/

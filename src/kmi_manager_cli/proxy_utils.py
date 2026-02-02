"""Shared proxy utility functions.

This module provides common utilities for working with proxy connections
that are used by both the CLI and doctor modules.
"""

import socket
from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.proxy import parse_listen


def proxy_listening(host: str, port: int) -> bool:
    """Check if a proxy is listening on the given host:port.
    
    Args:
        host: Hostname or IP address
        port: Port number
        
    Returns:
        True if a connection can be established, False otherwise
    """
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def normalize_connect_host(host: str) -> str:
    """Normalize host for client connections.
    
    Converts wildcard bind addresses to localhost for client connections.
    
    Args:
        host: The bind host (e.g., "0.0.0.0", "127.0.0.1", "::")
        
    Returns:
        Normalized host for client connections
    """
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def proxy_base_url(config: Config) -> str:
    """Build the proxy base URL from configuration.
    
    Args:
        config: Configuration object with proxy settings
        
    Returns:
        Full proxy base URL (e.g., "http://127.0.0.1:54123/kmi-rotor/v1")
    """
    host, port = parse_listen(config.proxy_listen)
    host = normalize_connect_host(host)
    scheme = "https" if config.proxy_tls_terminated else "http"
    return f"{scheme}://{host}:{port}{config.proxy_base_path}"


def proxy_daemon_log_path(config: Config) -> Path:
    """Get the path to the proxy daemon log file.
    
    Args:
        config: Configuration object
        
    Returns:
        Path to the daemon log file
    """
    log_dir = config.state_dir.expanduser() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "proxy.out"


def proxy_pid_path(config: Config) -> Path:
    """Get the path to the proxy PID file.
    
    Args:
        config: Configuration object
        
    Returns:
        Path to the PID file
    """
    pid_dir = config.state_dir.expanduser()
    pid_dir.mkdir(parents=True, exist_ok=True)
    return pid_dir / "proxy.pid"

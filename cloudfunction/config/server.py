import os
from typing import Optional

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")  # 监听地址
PORT = int(os.getenv("PORT", "8080"))  # 监听端口
SERVER_URL = os.getenv("SERVER_URL", f"http://{HOST}:{PORT}")  # 服务器URL

# SSL配置
SSL_ENABLED = os.getenv("SSL_ENABLED", "false").lower() == "true"
SSL_KEYFILE = os.getenv("SSL_KEYFILE")
SSL_CERTFILE = os.getenv("SSL_CERTFILE")
SSL_CA_CERTS = os.getenv("SSL_CA_CERTS")

# 代理配置
PROXY_HEADERS = os.getenv("PROXY_HEADERS", "true").lower() == "true"
TRUSTED_HOSTS = os.getenv("TRUSTED_HOSTS", "*").split(",")
FORWARDED_ALLOW_IPS = os.getenv("FORWARDED_ALLOW_IPS", "*").split(",")

# 并发配置
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "10"))
WORKERS = int(os.getenv("WORKERS", "1"))
BACKLOG = int(os.getenv("BACKLOG", "2048"))

# 超时配置
TIMEOUT_KEEP_ALIVE = int(os.getenv("TIMEOUT_KEEP_ALIVE", "5"))
TIMEOUT_GRACEFUL_SHUTDOWN = int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", "10"))
TIMEOUT_NOTIFY = int(os.getenv("TIMEOUT_NOTIFY", "30"))

# 清理配置
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "300"))

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
ACCESS_LOG = os.getenv("ACCESS_LOG", "true").lower() == "true" 
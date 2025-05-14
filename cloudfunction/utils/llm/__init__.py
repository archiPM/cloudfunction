# cloudfunction/utils/llm/__init__.py

import os
from .doubao_client import DoubaoClient
from .deepseek_client import DeepseekClient
from .minimax_client import MinimaxClient

def get_llm_client(provider: str = None):
    """
    获取LLM客户端实例
    
    Args:
        provider: 提供商名称 ('doubao', 'deepseek', 'minimax')
                 如果为None，则使用环境变量DEFAULT_LLM_PROVIDER指定的提供商
    """
    provider = provider or os.getenv('DEFAULT_LLM_PROVIDER', 'doubao')
    clients = {
        'doubao': DoubaoClient(),
        'deepseek': DeepseekClient(),
        'minimax': MinimaxClient()
    }
    return clients.get(provider)

__all__ = ['get_llm_client']
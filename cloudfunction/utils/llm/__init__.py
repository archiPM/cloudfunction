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

def get_llm_client_async(provider: str = None):
    """
    获取异步LLM客户端实例
    
    Args:
        provider: 提供商名称 ('doubao', 'deepseek', 'minimax')
                 如果为None，则使用环境变量DEFAULT_LLM_PROVIDER指定的提供商
    
    Returns:
        BaseLLMClient的实例，支持异步调用
    """
    # 返回与get_llm_client相同的客户端实例，但可以通过call_api_async方法进行异步调用
    return get_llm_client(provider)

__all__ = ['get_llm_client', 'get_llm_client_async']
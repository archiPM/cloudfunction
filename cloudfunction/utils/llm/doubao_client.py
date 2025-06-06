import os
from openai import OpenAI, AsyncOpenAI
from typing import List, Dict, Any, Optional

from .base_client import BaseLLMClient

class DoubaoClient(BaseLLMClient):
    """豆包 API 客户端"""
    
    def initialize_client(self) -> OpenAI:
        """初始化豆包客户端"""
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise ValueError("未设置ARK_API_KEY环境变量")
        
        return OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
    
    def initialize_async_client(self) -> AsyncOpenAI:
        """初始化异步豆包客户端"""
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise ValueError("未设置ARK_API_KEY环境变量")
        
        return AsyncOpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
    
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        return "doubao-1-5-pro-256k-250115"
    
    def get_model_context_window(self, model: str = None) -> int:
        """获取模型的上下文窗口大小（token数）"""
        model = model or self.get_default_model()
        
        # 模型上下文窗口映射
        window_sizes = {
            "doubao-1-5-pro-256k-250115": 262144,  # 256k token
            "doubao-1-5-lite-32k-250115": 32768,   # 32k token
            "doubao-1-5-pro-32k-250115": 32768,    # 新增: 32k token
        }
        
        return window_sizes.get(model, 32768)  # 默认返回32k作为保守估计
    
    def call_api(self, messages: List[Dict[str, str]], 
                model: Optional[str] = None,
                temperature: float = 0.7, 
                max_tokens: int = 1000,
                stream: bool = False) -> Any:
        """
        调用豆包 API
        
        Args:
            messages: 消息列表
            model: 模型名称，如果为None则使用默认模型
            temperature: 温度参数
            max_tokens: 最大生成token数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果
        """
        if model is None:
            model = self.get_default_model()
        
        try:
            self.logger.info(f"调用豆包 API，模型：{model}，上下文窗口：{self.get_model_context_window(model)} tokens")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            self.logger.info("成功调用豆包 API")
            return response
                
        except Exception as e:
            self.logger.error(f"调用豆包 API失败: {str(e)}")
            raise 
            
    async def call_api_async(self, messages: List[Dict[str, str]], 
                           model: Optional[str] = None,
                           temperature: float = 0.7, 
                           max_tokens: int = 1000,
                           stream: bool = False) -> Any:
        """
        异步调用豆包 API
        
        Args:
            messages: 消息列表
            model: 模型名称，如果为None则使用默认模型
            temperature: 温度参数
            max_tokens: 最大生成token数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果
        """
        if model is None:
            model = self.get_default_model()
        
        try:
            self.logger.info(f"异步调用豆包 API，模型：{model}，上下文窗口：{self.get_model_context_window(model)} tokens")
            
            response = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            self.logger.info("成功异步调用豆包 API")
            return response
                
        except Exception as e:
            self.logger.error(f"异步调用豆包 API失败: {str(e)}")
            raise 
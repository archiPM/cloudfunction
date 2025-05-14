import os
from openai import OpenAI
from typing import List, Dict, Any, Optional

from .base_client import BaseLLMClient

class DeepseekClient(BaseLLMClient):
    """Deepseek API 客户端"""
    
    def initialize_client(self) -> OpenAI:
        """初始化Deepseek客户端"""
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise ValueError("未设置ARK_API_KEY环境变量")
        
        return OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
    
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        return "deepseek-r1-250120"
    
    def get_model_context_window(self, model: str = None) -> int:
        """获取模型的上下文窗口大小（token数）"""
        model = model or self.get_default_model()
        
        # 模型上下文窗口映射
        window_sizes = {
            "deepseek-r1-250120": 65536,                 # 64k token
            "deepseek-r1-distill-qwen-32b-250120": 32768 # 新增: 32k token (蒸馏版)
        }
        
        return window_sizes.get(model, 32768)  # 默认返回32k
    
    def call_api(self, messages: List[Dict[str, str]], 
                model: Optional[str] = None,
                temperature: float = 0.7, 
                max_tokens: int = 1000,
                stream: bool = False) -> Any:
        """
        调用Deepseek API
        
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
            self.logger.info(f"调用Deepseek API，模型：{model}，上下文窗口：{self.get_model_context_window(model)} tokens")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            self.logger.info("成功调用Deepseek API")
            return response
                
        except Exception as e:
            self.logger.error(f"调用Deepseek API失败: {str(e)}")
            raise 
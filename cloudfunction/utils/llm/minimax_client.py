import os
from openai import OpenAI
from typing import List, Dict, Any, Optional

from .base_client import BaseLLMClient

class MinimaxClient(BaseLLMClient):
    """Minimax API 客户端"""
    
    def initialize_client(self) -> OpenAI:
        """初始化Minimax客户端"""
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("未设置MINIMAX_API_KEY环境变量")
        
        return OpenAI(
            api_key=api_key,
            base_url="https://api.minimax.chat/v1"
        )
    
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        return "minimax-text-01"  # 修改为官方正确的模型名
    
    def get_model_context_window(self, model: str = None) -> int:
        """获取模型的上下文窗口大小（token数）"""
        model = model or self.get_default_model()
        
        # 模型上下文窗口映射
        window_sizes = {
            "minimax-text-01": 1000192,  # 约100万token
            "abab6.5s": 245760,          # 约24万token，替换原来的abab5.5-chat
        }
        
        return window_sizes.get(model, 32768)  # 默认返回32k作为保守估计
    
    def call_api(self, messages: List[Dict[str, str]], 
                model: Optional[str] = None,
                temperature: float = 0.7, 
                max_tokens: int = 1000,
                stream: bool = False) -> Any:
        """
        调用Minimax API
        
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
            self.logger.info(f"调用Minimax API，模型：{model}，上下文窗口：{self.get_model_context_window(model)} tokens")
            
            # 获取群组ID（如果有）
            group_id = os.getenv("MINIMAX_GROUP_ID", "")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            self.logger.info("成功调用Minimax API")
            return response
                
        except Exception as e:
            self.logger.error(f"调用Minimax API失败: {str(e)}")
            raise 
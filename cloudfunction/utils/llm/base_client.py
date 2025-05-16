import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv

class BaseLLMClient(ABC):
    """
    大模型API调用的基类，定义通用接口
    """
    
    def __init__(self):
        # 配置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 加载环境变量
        load_dotenv()
        
        # 初始化客户端
        self._client = None
        self._async_client = None
    
    @property
    def name(self) -> str:
        """获取模型提供商名称"""
        return self.__class__.__name__.replace('Client', '').lower()
    
    @abstractmethod
    def initialize_client(self) -> Any:
        """初始化API客户端，由子类实现"""
        pass
    
    @abstractmethod
    def initialize_async_client(self) -> Any:
        """初始化异步API客户端，由子类实现"""
        pass
    
    @property
    def client(self) -> Any:
        """获取API客户端，如果未初始化则先初始化"""
        if self._client is None:
            self._client = self.initialize_client()
        return self._client
    
    @property
    def async_client(self) -> Any:
        """获取异步API客户端，如果未初始化则先初始化"""
        if self._async_client is None:
            self._async_client = self.initialize_async_client()
        return self._async_client
    
    @abstractmethod
    def get_default_model(self) -> str:
        """获取默认模型名称，由子类实现"""
        pass
    
    @abstractmethod
    def call_api(self, messages: List[Dict[str, str]], 
                model: Optional[str] = None,
                temperature: float = 0.7, 
                max_tokens: int = 1000,
                stream: bool = False) -> Any:
        """
        调用LLM API，由子类实现
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
            stream: 是否使用流式响应
        """
        pass
    
    @abstractmethod
    async def call_api_async(self, messages: List[Dict[str, str]],
                           model: Optional[str] = None,
                           temperature: float = 0.7,
                           max_tokens: int = 1000,
                           stream: bool = False) -> Any:
        """
        异步调用LLM API，由子类实现
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
            stream: 是否使用流式响应
        """
        pass
    
    def extract_content(self, response: Any) -> str:
        """从API响应中提取内容"""
        try:
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            return ""
        except Exception as e:
            self.logger.error(f"提取内容失败: {e}")
            return ""
    
    def parse_json_response(self, response: Any) -> Dict[str, Any]:
        """
        解析API响应中的JSON内容
        
        Args:
            response: API响应对象或文本内容
            
        Returns:
            解析后的JSON数据
        """
        if isinstance(response, str):
            content = response
        else:
            content = self.extract_content(response)
        
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 查找文本中的JSON部分
            json_match = re.search(r'({[\s\S]*})', content)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError as e:
                    self.logger.error(f"无法解析JSON: {e}")
                    raise
            else:
                self.logger.error("响应中未找到JSON内容")
                raise ValueError("响应中未找到有效的JSON内容")
    
    def analyze_text(self, text: str, 
                    system_prompt: Optional[str] = None,
                    model: Optional[str] = None,
                    temperature: float = 0.3) -> Dict[str, Any]:
        """
        分析文本并提取信息
        
        Args:
            text: 要分析的文本
            system_prompt: 系统提示词
            model: 使用的模型名称
            temperature: 温度参数
            
        Returns:
            分析结果（JSON）
        """
        if system_prompt is None:
            system_prompt = "你是一个专业的文本分析助手，擅长从文本中提取关键信息。请以JSON格式回复。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        try:
            response = self.call_api(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=1500,
                stream=False
            )
            
            return self.parse_json_response(response)
            
        except Exception as e:
            self.logger.error(f"文本分析失败: {str(e)}")
            raise 
    
    async def analyze_text_async(self, text: str,
                              system_prompt: Optional[str] = None,
                              model: Optional[str] = None,
                              temperature: float = 0.3) -> Dict[str, Any]:
        """
        异步分析文本并提取信息
        
        Args:
            text: 要分析的文本
            system_prompt: 系统提示词
            model: 使用的模型名称
            temperature: 温度参数
            
        Returns:
            分析结果（JSON）
        """
        if system_prompt is None:
            system_prompt = "你是一个专业的文本分析助手，擅长从文本中提取关键信息。请以JSON格式回复。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        try:
            response = await self.call_api_async(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=1500,
                stream=False
            )
            
            return self.parse_json_response(response)
            
        except Exception as e:
            self.logger.error(f"异步文本分析失败: {str(e)}")
            raise

    def get_model_context_window(self, model: str = None) -> int:
        """
        获取模型的上下文窗口大小（token数）
        由子类实现具体细节
        
        Args:
            model: 模型名称
            
        Returns:
            上下文窗口大小（token数）
        """
        return 4096  # 默认返回4k token作为保守估计 
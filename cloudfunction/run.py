#!/usr/bin/env python
"""
启动主进程的独立脚本
这种方式避免 Python 模块系统的循环导入问题
"""
import asyncio
import os
import sys
import logging
from cloudfunction.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    """主函数"""
    try:
        # 设置日志
        setup_logging()
        logger.info("正在启动服务...")
        
        # 延迟导入，避免循环依赖
        from cloudfunction.core.master import Master
        
        # 创建主进程管理器
        master = Master()
        
        # 启动服务
        await master.start()
        logger.info("服务启动完成")
        
        # 保持进程运行
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务被用户中断")
    except Exception as e:
        logger.error(f"服务异常退出: {str(e)}", exc_info=True)
        sys.exit(1) 
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class ProjectDatabaseManager:
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.engine = None
        self.SessionLocal = None
        self._init_db()
    
    def _init_db(self):
        """初始化项目级数据库连接"""
        try:
            # 加载项目级环境变量
            project_env_path = f"projects/{self.project_name}/.env"
            load_dotenv(project_env_path)
            
            # 获取数据库配置
            db_config = {
                'host': os.getenv('DB_HOST'),
                'port': int(os.getenv('DB_PORT', '3306')),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD'),
                'database': os.getenv('DB_NAME'),
                'pool_size': int(os.getenv('DB_POOL_SIZE', '20')),
                'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
                'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
                'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600'))
            }
            
            # 构建数据库URL
            db_url = f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            
            # 创建引擎
            self.engine = create_engine(
                db_url,
                pool_size=db_config['pool_size'],
                max_overflow=db_config['max_overflow'],
                pool_timeout=db_config['pool_timeout'],
                pool_recycle=db_config['pool_recycle'],
                pool_pre_ping=True
            )
            
            # 创建会话工厂
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info(f"数据库连接初始化成功: {self.project_name}")
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {str(e)}")
            raise
    
    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self):
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            logger.info(f"数据库连接已关闭: {self.project_name}") 
"""
数据库初始化脚本
启动服务前运行此脚本创建所有表
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.database import get_database


def init_database():
    """初始化数据库，创建所有表"""
    print("正在初始化数据库...")
    
    db = get_database()
    
    try:
        db.create_tables()
        print("✅ 数据库表创建成功！")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()

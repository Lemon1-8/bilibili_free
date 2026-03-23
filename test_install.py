"""
测试脚本 - 验证系统是否正确安装
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("=" * 50)
    print("检查 Python 版本...")
    version = sys.version_info
    print(f"当前版本: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 版本过低，需要 3.8+")
        return False
    print("✅ Python 版本符合要求")
    return True


def check_ffmpeg():
    """检查 FFmpeg"""
    print("\n" + "=" * 50)
    print("检查 FFmpeg...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            print(f"✅ FFmpeg 已安装: {lines[0]}")
            return True
    except FileNotFoundError:
        print("❌ FFmpeg 未安装")
        print("请访问 https://ffmpeg.org/download.html 安装")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n" + "=" * 50)
    print("检查依赖包...")
    
    required = [
        "fastapi",
        "uvicorn",
        "httpx",
        "requests",
        "openai",
        "sqlalchemy",
        "pydantic",
        "yaml",
    ]
    
    all_ok = True
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} 未安装")
            all_ok = False
    
    return all_ok


def check_project_structure():
    """检查项目结构"""
    print("\n" + "=" * 50)
    print("检查项目结构...")
    
    required_dirs = [
        "src/core",
        "src/models",
        "src/services",
        "src/api/routes",
        "config",
        "data",
    ]
    
    required_files = [
        "config/config.yaml",
        "main.py",
        "requirements.txt",
    ]
    
    all_ok = True
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path}/")
        else:
            print(f"❌ {dir_path}/ 不存在")
            all_ok = False
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} 不存在")
            all_ok = False
    
    return all_ok


def check_api_key():
    """检查 API Key"""
    print("\n" + "=" * 50)
    print("检查 API Key...")
    
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ 配置文件不存在")
        return False
    
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "REMOVED_DEEPSEEK_KEY" in content:
        print("✅ Deep Seek API Key 已配置")
        return True
    else:
        print("❌ Deep Seek API Key 未配置")
        return False


def main():
    print("\n" + "=" * 50)
    print("视频搞笑检测系统 - 安装检查")
    print("=" * 50)
    
    results = {
        "Python 版本": check_python_version(),
        "FFmpeg": check_ffmpeg(),
        "依赖包": check_dependencies(),
        "项目结构": check_project_structure(),
        "API Key": check_api_key(),
    }
    
    print("\n" + "=" * 50)
    print("检查结果汇总")
    print("=" * 50)
    
    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有检查通过！可以运行系统了。")
        print("\n启动命令:")
        print("  pip install -r requirements.txt")
        print("  python main.py")
    else:
        print("⚠️ 部分检查未通过，请先修复上述问题。")
    print("=" * 50)


if __name__ == "__main__":
    main()

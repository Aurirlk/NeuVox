#!/bin/bash
# 小智语音交互服务 - 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Python 环境
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    elif command -v python &> /dev/null; then
        PYTHON_CMD=python
    else
        print_error "Python 未安装"
        exit 1
    fi
    
    print_info "Python 版本: $($PYTHON_CMD --version)"
}

# 检查依赖
check_deps() {
    print_info "检查依赖..."
    $PYTHON_CMD -c "import fastapi, uvicorn, httpx, sqlalchemy" 2>/dev/null || {
        print_warn "缺少依赖，正在安装..."
        $PYTHON_CMD -m pip install -r requirements.txt
    }
}

# 创建必要目录
create_dirs() {
    mkdir -p uploads outputs logs
    print_info "目录创建完成"
}

# 启动服务
start_service() {
    print_info "启动服务..."
    
    if [ "$1" = "dev" ]; then
        print_info "开发模式启动 (自动重载)"
        $PYTHON_CMD main.py
    elif [ "$1" = "ui" ]; then
        print_info "启动 Gradio UI"
        $PYTHON_CMD voice_chat_ui.py
    else
        print_info "生产模式启动"
        $PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    fi
}

# 主函数
main() {
    echo "=========================================="
    echo "🎤 小智语音交互服务"
    echo "=========================================="
    
    check_python
    check_deps
    create_dirs
    
    MODE=${1:-dev}
    start_service $MODE
}

main "$@"

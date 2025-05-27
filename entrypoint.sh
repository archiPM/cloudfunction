#!/bin/bash
#用于在 sealos devbox 云平台工具进行部署，先使用 build.sh 构建，然后用 entrypoint.sh 进行启动，entrypoint.sh 需置于 project 根目录下

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
LOG_DIR="${SCRIPT_DIR}/cloudfunction/logs"
SERVER_LOG="${LOG_DIR}/server.log"
ERROR_LOG="${LOG_DIR}/error.log"
INIT_LOG="${LOG_DIR}/cloudfunction.log"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 记录启动信息到初始化日志
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 开始启动服务..." > "${INIT_LOG}"

# 检查并清理占用端口的进程
PORT=8080
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 检查端口 ${PORT} 占用情况..." >> "${INIT_LOG}"

# 清理所有 Python 相关进程
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 清理所有 Python 相关进程..." >> "${INIT_LOG}"
pkill -9 -f "python3 -m cloudfunction.run" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null

# 等待进程完全终止
sleep 3

# 检查端口占用
if lsof -i :${PORT} > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 发现端口 ${PORT} 仍被占用，尝试强制清理..." >> "${INIT_LOG}"
    # 获取所有占用端口的进程 PID
    PIDS=$(lsof -t -i :${PORT} 2>/dev/null)
    if [ ! -z "$PIDS" ]; then
        for PID in $PIDS; do
            echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 正在终止进程 PID: ${PID}" >> "${INIT_LOG}"
            kill -9 ${PID} 2>/dev/null
        done
        # 等待进程完全终止
        sleep 3
        # 再次检查端口是否已释放
        if lsof -i :${PORT} > /dev/null 2>&1; then
            echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 警告：无法释放端口 ${PORT}" >> "${ERROR_LOG}"
            exit 1
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 端口 ${PORT} 已成功释放" >> "${INIT_LOG}"
        fi
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 端口 ${PORT} 未被占用" >> "${INIT_LOG}"
fi

# 检查系统虚拟环境是否存在
if [ ! -d "${SCRIPT_DIR}/cloudfunction_venv" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 错误：系统虚拟环境不存在，请先运行 build.sh" >> "${ERROR_LOG}"
    exit 1
fi

# 激活虚拟环境
source "${SCRIPT_DIR}/cloudfunction_venv/bin/activate"

# 检查全局环境变量文件
if [ -f "${SCRIPT_DIR}/cloudfunction/.env" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 加载全局环境变量..." >> "${INIT_LOG}"
    set -a
    source "${SCRIPT_DIR}/cloudfunction/.env"
    set +a
fi

# 启动服务
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 启动服务..." >> "${INIT_LOG}"
# 使用新的启动脚本，避免循环导入问题
python3 -m cloudfunction.run 
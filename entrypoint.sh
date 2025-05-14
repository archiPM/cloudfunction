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
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 开始启动服务..." >> "${INIT_LOG}"

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
python3 -m cloudfunction.core.master >> "${SERVER_LOG}" 2>> "${ERROR_LOG}" 
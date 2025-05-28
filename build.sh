#!/bin/bash

# 创建日志目录
mkdir -p cloudfunction/logs
LOG_FILE="cloudfunction/logs/build.log"

echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 开始构建云函数服务..." > "$LOG_FILE"

# 检查并创建系统虚拟环境
if [ ! -d "cloudfunction_venv" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建系统虚拟环境..." >> "$LOG_FILE"
    python3 -m venv cloudfunction_venv
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 系统虚拟环境创建完成" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 系统虚拟环境已存在，跳过创建" >> "$LOG_FILE"
fi

# 激活系统虚拟环境
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 激活系统虚拟环境..." >> "$LOG_FILE"
source cloudfunction_venv/bin/activate

# 检查并更新系统级依赖
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 安装系统级依赖..." >> "$LOG_FILE"
pip install -r cloudfunction/requirements.txt >> "$LOG_FILE" 2>&1

# 创建必要的系统目录
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 检查并创建必要的目录..." >> "$LOG_FILE"

# 检查并创建日志目录
if [ ! -d "cloudfunction/logs" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建日志目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/logs
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 日志目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查并创建虚拟环境目录
if [ ! -d "cloudfunction/venvs" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建虚拟环境目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/venvs
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 虚拟环境目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查并创建工具类目录
if [ ! -d "cloudfunction/utils" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建工具类目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/utils
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 工具类目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查并创建项目目录
if [ ! -d "cloudfunction/projects" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建项目目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/projects
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 项目目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查并创建项目日志目录
if [ ! -d "cloudfunction/logs/projects" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建项目日志目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/logs/projects
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 项目日志目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查并创建配置目录
if [ ! -d "cloudfunction/config" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建配置目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/config
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 配置目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 检查调度器配置文件
if [ ! -f "cloudfunction/config/scheduler_config.yaml" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 警告：调度器配置文件不存在" >> "$LOG_FILE"
fi

# 检查并创建任务目录
if [ ! -d "cloudfunction/tasks" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 创建任务目录..." >> "$LOG_FILE"
    mkdir -p cloudfunction/tasks
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 任务目录已存在，跳过创建" >> "$LOG_FILE"
fi

# 设置权限
echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 设置文件权限..." >> "$LOG_FILE"

# 检查并设置入口脚本权限
if [ -f "cloudfunction_entry.sh" ]; then
    if [ ! -x "cloudfunction_entry.sh" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 设置入口脚本执行权限..." >> "$LOG_FILE"
        chmod +x cloudfunction_entry.sh
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 入口脚本已有执行权限，跳过设置" >> "$LOG_FILE"
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 警告：入口脚本不存在" >> "$LOG_FILE"
fi

# 检查并设置重启脚本权限
if [ -f "cloudfunction/restart.sh" ]; then
    if [ ! -x "cloudfunction/restart.sh" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 设置重启脚本执行权限..." >> "$LOG_FILE"
        chmod +x cloudfunction/restart.sh
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 重启脚本已有执行权限，跳过设置" >> "$LOG_FILE"
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 警告：重启脚本不存在" >> "$LOG_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S %Z') - 系统环境构建完成" >> "$LOG_FILE" 
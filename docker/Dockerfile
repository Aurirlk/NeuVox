# NeuVox 语音服务 Dockerfile
# 多阶段构建

# ==================== 阶段 1: 构建 ====================
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==================== 阶段 2: 运行 ====================
FROM python:3.11-slim as runtime

WORKDIR /app

# 从构建阶段复制依赖
COPY --from=builder /install /usr/local

# 创建非 root 用户
RUN groupadd -r neuvox && useradd -r -g neuvox neuvox

# 创建必要目录
RUN mkdir -p uploads outputs data/Knowledge logs && \
    chown -R neuvox:neuvox /app

# 复制应用代码
COPY --chown=neuvox:neuvox . .

# 切换到非 root 用户
USER neuvox

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health')" || exit 1

# 启动命令
CMD ["uvicorn", "fastAPI:app", "--host", "0.0.0.0", "--port", "8000"]

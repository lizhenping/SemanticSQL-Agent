FROM python:3.11-slim

WORKDIR /app

# 系统依赖（sqlite3 客户端供调试，git 不需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 层缓存）
COPY semanticsql-agent/requirements.txt /app/requirements.txt
# pip 走国内加速（清华源），构建更快
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY semanticsql-agent /app

# history 输出目录
RUN mkdir -p /app/history

# 默认入口：cli.py
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]

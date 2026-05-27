FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置系统环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 🌟 核心防御：针对企业内网代理/防火墙，强制关闭 APT 的 SSL 证书校验
RUN echo "Acquire::https::Verify-Peer \"false\";" > /etc/apt/apt.conf.d/99-disable-cert-check && \
    echo "Acquire::http::Verify-Peer \"false\";" >> /etc/apt/apt.conf.d/99-disable-cert-check

# 🌟 核心防御：安装生成 PDF (xhtml2pdf / pycairo) 所需的底层 C++ 编译器和图形库依赖
RUN apt-get update -o Acquire::https::Verify-Peer=false || true && \
    apt-get install -y -o Acquire::https::Verify-Peer=false \
    build-essential \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖描述文件
COPY requirements.txt .

# 🌟 核心防御：在内网打包时，强行指定清华源，并把超时时间拉长到 1000 秒，防止 pip 安装超时流产
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt  --default-timeout=1000

# 复制其余项目代码
COPY . .

# 暴露端口声明（提示作用）
EXPOSE 8001

# 启动命令：交给 uvicorn 托管
CMD ["python", "main.py"]
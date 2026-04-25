FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置模型存放路径的环境变量（构建时和运行时都会生效）
# 建议放在 /app 目录下，方便管理
ENV PKUSEG_HOME=/app/pkuseg_data
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV VECLIB_MAXIMUM_THREADS=1
ENV BLIS_NUM_THREADS=1

# 1. 复制依赖声明文件
COPY pyproject.toml ./
COPY setup.cfg* ./

# 2. 安装依赖
# 注意：此时会安装 spacy_pkuseg 等库
RUN pip install --no-cache-dir .

# ---------------------------------------------------------
# 🌟 新增：在构建阶段预下载模型
# 这一步必须在安装完依赖之后、复制业务代码之前（利用缓存）
# ---------------------------------------------------------
RUN python -c "import spacy_pkuseg; spacy_pkuseg.pkuseg(model_name='mixed')"

# 3. 复制项目代码
COPY . .

# 4. 暴露端口
EXPOSE 8001
ENV APP_ENV=production
# 5. 启动命令
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1 --limit-concurrency 8 --backlog 64 --timeout-keep-alive 10"]
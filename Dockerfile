FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# 安装系统构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-dotenv gunicorn whitenoise

COPY . .

# 收集静态文件
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# 用 Gunicorn 启动，而不是 runserver
CMD ["gunicorn", "tms.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "120"]

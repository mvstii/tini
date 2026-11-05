FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" || true
COPY . .
RUN pip install --no-cache-dir -e .
# Proxy arkasında (Render) gerçek istemci IP'si için --proxy-headers şart: yoksa giriş/kayıt hız
# sınırı tüm kullanıcıları tek IP sayar. Göç açılışta uygulanır (prod compose ile aynı).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]

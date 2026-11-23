FROM python:3.12-slim
WORKDIR /app
COPY . .
# Yalnızca çalışma bağımlılıkları (pytest/ruff imaja girmez); kurulum hatası derlemeyi düşürür.
RUN pip install --no-cache-dir .
# Root olmayan kullanıcı: kapsayıcı ele geçirilirse yetki sınırlı kalır.
RUN useradd --create-home --uid 10001 tini && chown -R tini:tini /app
USER tini
# Proxy arkasında (Render) gerçek istemci IP'si için --proxy-headers şart: yoksa giriş/kayıt hız
# sınırı tüm kullanıcıları tek IP sayar. FORWARDED_ALLOW_IPS ortamdan gelir (varsayılan '*':
# Render ön yüzünün IP'leri sabit değil). Göç açılışta uygulanır (prod compose ile aynı).
ENV FORWARDED_ALLOW_IPS='*'
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=\"$FORWARDED_ALLOW_IPS\""]

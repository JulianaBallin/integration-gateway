FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN addgroup -g 1000 appgroup && adduser -D -u 1000 -G appgroup appuser

WORKDIR /app
COPY requirements.txt .
RUN apk add --no-cache postgresql-client-libs || true
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
RUN chown -R appuser:appgroup /app

USER appuser

CMD ["python", "app.py"]

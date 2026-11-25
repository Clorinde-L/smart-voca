# 2026-11-25 - smart-voca - 학교 서버 배포용 이미지 (Dockerfile 구성 R-01~R-16, 결정 기록 ADR-29)
# 파일 위치: Dockerfile
FROM python:3.12-slim

# 바이트코드(.pyc)를 쓰지 않는다: 실행 중에는 /data·/tmp 말고는 쓸 수 없다
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HOME=/tmp \
    DB_PATH=/data/voca.db

WORKDIR /app

# 의존성 먼저: 소스만 바뀌면 이 층은 캐시를 다시 쓴다 (R-13)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data ./data

# UID 10001 사용자와 /data (SQLite 파일 위치). 서버가 붙이는 저장 공간이 이 소유자를 물려받는다 (R-05, R-06)
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin voca \
    && mkdir -p /data \
    && chown 10001:10001 /data

USER 10001
EXPOSE 8080

# 운영 서버 gunicorn. 워커는 1개: 진행 중인 카드·시험 상태를 서버 메모리에 둔다 (ADR-20, ADR-29)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "60", "--access-logfile", "-", "smartvoca.web.wsgi:app"]

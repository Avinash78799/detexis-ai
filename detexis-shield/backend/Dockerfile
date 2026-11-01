FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
COPY sensor-sdk /sensor-sdk
RUN pip install --no-cache-dir -r requirements.txt /sensor-sdk
COPY backend/app ./app
COPY backend/create_site.py ./
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN useradd --uid 10001 --create-home shield
USER 10001
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000
CMD ["lexnusa-api"]

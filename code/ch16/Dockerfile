# Text only: not built or run for this book.
# Build from the code folder: docker build -f ch16/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV HOST=0.0.0.0 PORT=8016 PYTHONUNBUFFERED=1
EXPOSE 8016
USER nobody
CMD ["python", "-m", "ch16.app"]

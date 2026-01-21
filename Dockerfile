FROM python:3.11-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deskbird.py api.py ./
EXPOSE 2713
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "2713"]

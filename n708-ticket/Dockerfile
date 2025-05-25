FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_APP=app.py
ENV PORT=5002
CMD ["gunicorn", "-b", "0.0.0.0:5002", "app:app"]

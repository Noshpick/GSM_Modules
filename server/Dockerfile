FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN apt update && apt install -y sqlite3
CMD ["python", "main.py"]

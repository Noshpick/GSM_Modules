FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install nano
RUN apt-get update && apt-get install sqlite3
CMD ["python", "main.py"]

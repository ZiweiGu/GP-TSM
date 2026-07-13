FROM python:3.9.5-slim
WORKDIR /app

COPY requirements.txt .
COPY docker/api-requirements.txt .

RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2 
RUN pip install -r api-requirements.txt
RUN pip install -r requirements.txt

COPY promptengine/ .
COPY app.py .
COPY diff_text.py .
COPY eval_response.py .
COPY gptsm-lite.py .
COPY llm.py .
COPY phrase_splitter.py .
COPY .env .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
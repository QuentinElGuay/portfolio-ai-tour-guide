FROM apache/airflow:3.3.1-python3.12

RUN pip install --no-cache-dir \
    apache-airflow-providers-docker==4.5.9 \
    apache-airflow-providers-fab==3.8.0

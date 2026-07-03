import csv
from elasticsearch import Elasticsearch
import os
import psycopg2


db_host = os.getenv("DB_HOST", "127.0.0.1")
db_port = "5432" if db_host == "db" else "5434"

db_connection = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "search_db"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    host=db_host,
    port=db_port,
)


db_cursor = db_connection.cursor()

es_host = os.getenv("ES_HOST", "localhost")
es_client = Elasticsearch(f"http://{es_host}:9200", request_timeout=30)


# Инициализация структур данных
def init_services():
    # Использование SERIAL PRIMARY KEY для автоматической генерации ID на стороне СУБД
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        rubrics TEXT NOT NULL,
        text TEXT NOT NULL,
        created_date TIMESTAMP NOT NULL
        );
    """)
    db_connection.commit()

    # Инициализация индекса в ElasticSearch
    if not es_client.indices.exists(index='documents'):
        es_client.indices.create(index='documents')

    print('Инициализация БД и ElasticSearch успешно завершена!')


def load_csv_to_services():
    with open('posts.csv', mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        # Индексация документов с генерацией уникальных ID через enumerate
        for doc_id, row in enumerate(reader, 1):
            rubrics = row['rubrics']
            text = row['text']
            created_date = row['created_date']

            # Дублирование данных: сохранение полной реплики в PostgreSQL
            db_cursor.execute(
                """INSERT INTO documents (id, rubrics, text, created_date) VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;""",
                (doc_id, rubrics, text, created_date)
            )

            # Индексация текстового поля в ElasticSearch для полнотекстового поиска
            es_client.index(
                index='documents',
                id=doc_id,
                document={'id': doc_id, 'text': text}
            )
    db_connection.commit()
    print('Все данные из CSV успешно загружены в базу и поисковый индекс!')


if __name__ == '__main__':
    init_services()
    load_csv_to_services()

    db_cursor.close()
    db_connection.close()



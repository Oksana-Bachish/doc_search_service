from fastapi import FastAPI, Query, HTTPException
import psycopg2
import os
from psycopg2.extras import RealDictCursor
from elasticsearch import Elasticsearch

app = FastAPI(ttile='Поисковый сервис документов')

# Конфигурация клиентов из переменных окружения (Docker Compose)
es_host = os.getenv("ES_HOST", "localhost")
es_client = Elasticsearch(f"http://{es_host}:9200", request_timeout=30)


def get_db_connection():
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    # Использование RealDictCursor для получения результатов в формате словарей (dict)
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "search_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=db_host,
        port='5432' if db_host == 'db' else '5434',
        cursor_factory=RealDictCursor
    )


@app.get('/search')
async def search_documents(text: str = Query(..., description="Текст для поиска по документам")):
    search_query = {
        'match': {
            'text': text
        }
    }
    es_response = es_client.search(index='documents', query=search_query, size=20)

    hits = es_response['hits']['hits']
    if not hits:
        return []

    found_ids = [int(hit['_id']) for hit in hits]

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, rubrics, text, created_date FROM documents WHERE id IN %s ORDER BY created_date DESC;",
        (tuple(found_ids),)
    )

    db_documents = cursor.fetchall()

    cursor.close()
    connection.close()

    return db_documents


@app.delete('/document/{doc_id}')
async def delete_document(doc_id:int):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute('SELECT id FROM documents WHERE id = %s', (doc_id,))
    if not cursor.fetchone():
        cursor.close()
        connection.close()
        # Если документа нет, отдаем ошибку 404 (Не найдено)
        raise HTTPException(status_code=404, detail='Документ с таким ID не найден в базе')

    # Удаляем запись из PostgreSQL
    cursor.execute('DELETE FROM documents WHERE id=%s;', (doc_id,))
    connection.commit()
    cursor.close()
    connection.close()

    # Удаляем запись из индекса ElasticSearch
    try:
        es_client.delete(index='documents', id=doc_id)
    except Exception:
        pass

    return {'status': 'success', 'message': f"Документ с ID {doc_id} успешно удален из БД и индекса"}

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from main import app, es_client

client = TestClient(app)

def test_search_documents_success(mocker):
    """Успешный поиск: ElasticSearch вернул совпадения, Postgres выдал документы."""
    # Имитация ответа от индекса ElasticSearch
    mock_es_response = {
        'hits': {
            'hits': [
                {'_id': '10'},
                {'_id': 20}
            ]
        }
    }

    mock_es = mocker.patch.object(es_client, 'search', return_value=mock_es_response)

    # Имитация строк из таблицы PostgreSQL
    mock_db_data = [
        {'id': 10, 'rubrics': 'Тест', 'text': 'Первый документ', 'create_date': '2026-10-30'},
        {'id': 10, 'rubrics': 'Тест', 'text': 'Второй документ', 'create_date': '2026-10-29'}
    ]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_db_data

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Перехват функции подключения к БД
    mocker.patch('main.get_db_connection', return_value=mock_conn)

    # Выполнение запроса к эндпоинту
    response = client.get('/search?text=питон')

    # Валидация ответа сервера
    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data) == 2
    assert json_data[0]['text'] == 'Первый документ'

    # Проверка, что эндпоинт вызывал ElasticSearch
    assert mock_es.called
    called_kwargs = mock_es.call_args.kwargs
    assert called_kwargs['index'] == 'documents'

    # Проверка, что в SQL-запрос улетели правильные ID документов
    mock_cursor.execute.assert_called_once()
    assert (10, 20) in mock_cursor.execute.call_args[0][1]



def test_search_documents_empty(mocker):
    """Пустой поиск: ElasticSearch ничего не нашел, обращений к БД нет."""
    # Имитация пустого ответа поискового движка
    mock_es_response = {'hits': {'hits': []}}
    mocker.patch.object(es_client, 'search', return_value=mock_es_response)

    mock_get_db = mocker.patch('main.get_db_connection')

    response = client.get('/search?text=ничего')

    # Проверка, что вернулся пустой список и БД не вызывалась
    assert response.status_code == 200
    assert response.json() == []
    assert not mock_get_db.called


def test_delete_document_success(mocker):
    """Успешное удаление: документ найден в Postgres и удален из обеих баз."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('main.get_db_connection', return_value=mock_conn)

    mock_es_delete = mocker.patch.object(es_client, 'delete')

    response = client.delete('/document/1')

    # Проверка подтверждения транзакции и запроса к ElasticSearch
    assert response.status_code == 200
    assert response.json()['status'] == 'success'
    assert mock_conn.commit.called
    mock_es_delete.assert_called_once_with(index='documents', id=1)


def test_delete_document_not_found(mocker):
    """Ошибка удаления: документ отсутствует в БД, возврат 404"""
    # Имитируем, что fetchone вернул None (запись не найдена)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('main.get_db_connection', return_value=mock_conn)

    response = client.delete('/document/999')

    # Проверка статус-кода ошибки
    assert response.status_code == 404
    assert response.json()['detail'] == 'Документ с таким ID не найден в базе'

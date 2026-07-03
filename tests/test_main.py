import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_search_endpoint():
    """Test that the search endpoint returns 200 OK and a list of documents."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/search", params={"text": "актуальность"})

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_delete_non_existent_document():
    """Test that deleting a non-existent document returns 404 Not Found."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/document/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Документ с таким ID не найден в базе"
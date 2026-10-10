def test_list_products_returns_created_products(client):
    """Regression test: GET /products was missing entirely (only POST existed), so the
    Products & Plans page could never load its own list after creating a product."""
    created = client.post("/products", json={"name": "Billing Platform", "code": "core"}).json()

    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert any(p["id"] == created["id"] and p["name"] == "Billing Platform" for p in products)


def test_list_products_is_scoped_to_tenant_and_workspace(client):
    client.post(
        "/products",
        json={"name": "Demo Product", "code": "demo-prod"},
        headers={"X-Tenant-Id": "DEMO", "X-Workspace-Type": "demo"},
    )
    client.post(
        "/products",
        json={"name": "My Product", "code": "my-prod"},
        headers={"X-Tenant-Id": "TENANT_1", "X-Workspace-Type": "production"},
    )

    demo_products = client.get(
        "/products", headers={"X-Tenant-Id": "DEMO", "X-Workspace-Type": "demo"}
    ).json()
    my_products = client.get(
        "/products", headers={"X-Tenant-Id": "TENANT_1", "X-Workspace-Type": "production"}
    ).json()

    assert any(p["code"] == "demo-prod" for p in demo_products)
    assert not any(p["code"] == "my-prod" for p in demo_products)
    assert any(p["code"] == "my-prod" for p in my_products)
    assert not any(p["code"] == "demo-prod" for p in my_products)

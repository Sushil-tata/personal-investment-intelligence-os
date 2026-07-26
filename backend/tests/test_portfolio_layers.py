from fastapi.testclient import TestClient

from piios_backend.main import app


def test_family_registry_and_layers_exist() -> None:
    with TestClient(app) as client:
        family = client.get('/api/v1/family/portfolios')
        assert family.status_code == 200
        assert family.json()['households']

        ips = client.get('/api/v1/ips/constraints')
        assert ips.status_code == 200
        assert ips.json()['constraints']

        instruments = client.get('/api/v1/instruments')
        assert instruments.status_code == 200
        assert instruments.json()['instruments']

        trust = client.get('/api/v1/data-trust/hierarchy')
        assert trust.status_code == 200
        assert trust.json()['hierarchy']


def test_portfolio_analytics_endpoints() -> None:
    with TestClient(app) as client:
        net_worth = client.get('/api/v1/portfolio/net-worth')
        assert net_worth.status_code == 200
        payload = net_worth.json()
        assert payload['net_worth'] == payload['total_assets'] - payload['total_liabilities']

        allocation = client.get('/api/v1/portfolio/allocation', params={'dimension': 'asset_class'})
        assert allocation.status_code == 200
        assert allocation.json()['items']

        currency = client.get('/api/v1/portfolio/currency-exposure')
        assert currency.status_code == 200
        assert currency.json()['items']

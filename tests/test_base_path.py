from fastapi.testclient import TestClient
from app.main import create_app, create_user


def test_prefixed_login_assets_export_and_tunnel_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv('CABLEPLAN_DATA', str(tmp_path))
    monkeypatch.setenv('CABLEPLAN_BASE_PATH', '/cableplan')
    monkeypatch.setenv('CABLEPLAN_PROXY_MODE', 'nginx')
    app = create_app()
    create_user('prefixadmin', 'password-test-123')
    with TestClient(app, base_url='https://www.pigeonfou.com') as client:
        headers={'x-cableplan-access-channel':'lan'}
        page=client.get('/cableplan/',headers=headers)
        assert page.status_code==200
        assert '/cableplan/static/app.js' in page.text
        assert client.get('/cableplan/static/app.js',headers=headers).status_code==200
        response=client.post('/cableplan/api/login',json={'username':'prefixadmin','password':'password-test-123'},headers=headers)
        assert response.status_code==200
        assert 'Path=/cableplan/' in response.headers['set-cookie']
        headers['x-csrf-token']=response.json()['csrf']
        project=client.post('/cableplan/api/projects',json={'name':'Prefix test'},headers=headers).json()
        aid=client.get('/cableplan/api/projects/'+project['id']+'/assemblies',headers=headers).json()[0]['id']
        response=client.get('/cableplan/api/assemblies/'+aid+'/export/pdf',headers=headers)
        assert response.status_code==200 and response.content.startswith(b'%PDF')
        assert client.get('/cableplan/health',headers={'x-cableplan-access-channel':'tunnel'}).status_code==403
        assert client.get('/doctrad/health',headers=headers).status_code==404

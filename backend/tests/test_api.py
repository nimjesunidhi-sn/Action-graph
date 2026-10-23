import os
import pytest
os.environ['DATABASE_URL']='sqlite:///./test_actiongraph.db'
os.environ['STORAGE_DIR']='./test_storage'
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import Base,engine

client=TestClient(app)
@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

def account(email):
    r=client.post('/api/auth/register',json={'name':'Tester','email':email,'password':'password123'}); assert r.status_code==200; return {'Authorization':'Bearer '+r.json()['access_token']}
def test_auth_and_owner_isolation():
    h1=account('one@example.com'); h2=account('two@example.com')
    assert client.get('/api/auth/me').status_code==401
    r=client.post('/api/tasks',headers=h1,json={'title':'Prepare launch','status':'pending'}); assert r.status_code==200
    assert client.get('/api/tasks',headers=h2).json()['total']==0
    assert client.get('/api/tasks/1',headers=h2).status_code==404
def test_txt_mock_pipeline_and_stats():
    h=account('meeting@example.com')
    data={'file':('sync.txt',b'We agreed to launch next week. Maya will prepare the release checklist. There is a risk of delay because testing is blocked.','text/plain')}
    up=client.post('/api/meetings',headers=h,files=data,data={'title':'Launch sync'}); assert up.status_code==200
    mid=up.json()['meeting']['id']; done=client.post(f'/api/meetings/{mid}/process',headers=h); assert done.status_code==200,done.text
    assert done.json()['ai_mode']=='mock' and done.json()['transcript']
    assert len(done.json()['tasks'])>=1 and len(done.json()['decisions'])>=1 and len(done.json()['risks'])>=1
    task=done.json()['tasks'][0]; assert task['status']=='needs_review'
    assert client.post(f"/api/tasks/{task['id']}/approve",headers=h).json()['status']=='pending'
    assert client.get('/api/dashboard/stats',headers=h).json()['tasks']>=1
def test_upload_validation():
    h=account('badfile@example.com')
    r=client.post('/api/meetings',headers=h,files={'file':('bad.exe',b'no','application/octet-stream')})
    assert r.status_code==415

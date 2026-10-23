from pathlib import Path
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings
from app.db.database import Base, engine, get_db
from app.models import User, Meeting, Task, Decision, Risk
from app.schemas import Register, Login, TaskInput, TaskPatch, MeetingPatch, DecisionPatch, RiskPatch
from app.security import hash_password, verify_password, make_token, current_user
from app.services.document_service import extract_text, ALLOWED
from app.services.extraction_service import extract

Base.metadata.create_all(bind=engine)
Path(settings.storage_dir).mkdir(parents=True,exist_ok=True)
app=FastAPI(title='ActionGraph API',version='1.0.0',description='Meeting intelligence and action tracking API')
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
def owned_meeting(db, uid, mid):
    m=db.query(Meeting).filter_by(id=mid,user_id=uid).first()
    if not m: raise HTTPException(404,'Meeting not found')
    return m
def task_json(t): return {'id':t.id,'title':t.title,'description':t.description,'owner':t.owner,'due_date':t.due_date,'priority':t.priority,'status':t.status,'evidence':t.evidence,'confidence':t.confidence,'ai_generated':t.ai_generated,'meeting_id':t.meeting_id,'meeting_title':t.meeting.title if t.meeting else None,'created_at':t.created_at,'updated_at':t.updated_at}
def meeting_json(m): return {'id':m.id,'title':m.title,'meeting_date':m.meeting_date,'project':m.project,'participants':m.participants,'status':m.status,'summary':m.summary,'transcript':m.transcript,'source_name':m.source_name,'ai_mode':m.ai_mode,'error':m.error,'created_at':m.created_at,'task_count':len(m.tasks),'decision_count':len(m.decisions),'risk_count':len(m.risks)}
@app.get('/api/health')
def health(): return {'status':'ok','ai_provider':settings.ai_provider}
@app.post('/api/auth/register')
def register(body:Register,db:Session=Depends(get_db)):
    email=body.email.lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,'An account with this email already exists.')
    u=User(name=body.name.strip(),email=email,password_hash=hash_password(body.password)); db.add(u); db.commit(); db.refresh(u)
    return {'access_token':make_token(u.id),'token_type':'bearer','user':{'id':u.id,'name':u.name,'email':u.email}}
@app.post('/api/auth/login')
def login(body:Login,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=body.email.lower()).first()
    if not u or not verify_password(body.password,u.password_hash): raise HTTPException(401,'Email or password is incorrect.')
    return {'access_token':make_token(u.id),'token_type':'bearer','user':{'id':u.id,'name':u.name,'email':u.email}}
@app.get('/api/auth/me')
def me(u:User=Depends(current_user)): return {'id':u.id,'name':u.name,'email':u.email}
@app.post('/api/meetings')
async def upload_meeting(file:UploadFile=File(...),title:str=Form(''),meeting_date:date|None=Form(None),project:str|None=Form(None),participants:str|None=Form(None),db:Session=Depends(get_db),u:User=Depends(current_user)):
    ext=Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED: raise HTTPException(415,'Unsupported file type. Upload TXT, Markdown, PDF, DOCX, SRT, VTT, MP3, WAV, MP4, M4A, MOV, or WEBM.')
    data=await file.read(settings.max_upload_mb*1024*1024+1)
    if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,f'File exceeds the {settings.max_upload_mb} MB upload limit.')
    import uuid
    stored=Path(settings.storage_dir)/f'{uuid.uuid4().hex}{ext}'; stored.write_bytes(data)
    m=Meeting(user_id=u.id,title=(title or Path(file.filename).stem)[:240],meeting_date=meeting_date,project=project,participants=participants,source_name=Path(file.filename).name,source_path=str(stored.resolve()),status='uploaded')
    db.add(m); db.commit(); db.refresh(m)
    return {'meeting':meeting_json(m),'message':'Upload complete. Start processing when ready.'}
@app.get('/api/meetings')
def meetings(search:str='',status:str='',skip:int=0,limit:int=50,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Meeting).filter_by(user_id=u.id)
    if search: q=q.filter(Meeting.title.ilike(f'%{search}%'))
    if status: q=q.filter_by(status=status)
    rows=q.order_by(Meeting.created_at.desc()).offset(skip).limit(min(limit,100)).all()
    return {'items':[meeting_json(m) for m in rows],'total':q.count()}
@app.get('/api/meetings/{mid}')
def meeting_detail(mid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid); d=meeting_json(m)
    d.update(tasks=[task_json(t) for t in m.tasks],decisions=[{'id':x.id,'title':x.title,'description':x.description,'evidence':x.evidence,'confidence':x.confidence} for x in m.decisions],risks=[{'id':x.id,'description':x.description,'severity':x.severity,'suggested_resolution':x.suggested_resolution,'evidence':x.evidence,'status':x.status,'note':x.note} for x in m.risks]); return d
def process(m,db):
    try:
        path=Path(m.source_path or '')
        if not path.is_file(): raise ValueError('Uploaded source file is no longer available. Re-upload it to retry processing.')
        transcript=extract_text(path)
        if not transcript.strip(): raise ValueError('No readable transcript text was found in this file.')
        # Reprocessing replaces AI output for this meeting instead of duplicating it.
        old_ai=db.query(Task).filter_by(meeting_id=m.id,user_id=m.user_id,ai_generated=True,status='needs_review').all()
        for old in old_ai: db.delete(old)
        existing_titles={t.title.casefold() for t in db.query(Task).filter_by(meeting_id=m.id,user_id=m.user_id).all()}
        db.query(Decision).filter_by(meeting_id=m.id,user_id=m.user_id).delete()
        db.query(Risk).filter_by(meeting_id=m.id,user_id=m.user_id).delete()
        result,mode=extract(transcript,m.meeting_date); m.transcript=transcript; m.summary=result.summary; m.ai_mode=mode; m.status='processed'; m.error=None
        for item in result.action_items:
            if item.title.casefold() in existing_titles: continue
            db.add(Task(user_id=m.user_id,meeting_id=m.id,title=item.title,description=item.description,owner=item.owner,due_date=item.due_date,priority=item.priority,status='needs_review',evidence=item.evidence,confidence=item.confidence,ai_generated=True))
        for item in result.decisions: db.add(Decision(user_id=m.user_id,meeting_id=m.id,title=item.title,description=item.description,evidence=item.evidence,confidence=item.confidence))
        for item in result.risks_and_blockers: db.add(Risk(user_id=m.user_id,meeting_id=m.id,description=item.description,severity=item.severity,suggested_resolution=item.suggested_resolution,evidence=item.evidence,confidence=item.confidence))
        db.commit()
    except Exception as ex:
        db.rollback(); m=db.get(Meeting,m.id); m.status='failed'; m.error=str(ex)[:500]; db.commit(); raise HTTPException(422,str(ex))
@app.post('/api/meetings/{mid}/process')
def process_meeting(mid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid); process(m,db); return meeting_detail(mid,db,u)
@app.get('/api/meetings/{mid}/status')
def meeting_status(mid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid); return {'status':m.status,'error':m.error,'ai_mode':m.ai_mode}
@app.get('/api/meetings/{mid}/transcript')
def transcript(mid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid); return {'transcript':m.transcript}
@app.patch('/api/meetings/{mid}')
def patch_meeting(mid:int,b:MeetingPatch,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid)
    for k,v in b.model_dump(exclude_unset=True).items(): setattr(m,k,v)
    db.commit(); db.refresh(m); return meeting_json(m)
@app.delete('/api/meetings/{mid}')
def delete_meeting(mid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    m=owned_meeting(db,u.id,mid); source=Path(m.source_path) if m.source_path else None; db.delete(m); db.commit()
    if source and source.is_file(): source.unlink(missing_ok=True)
    return {'ok':True}
@app.get('/api/tasks')
def tasks(search:str='',status:str='',priority:str='',owner:str='',meeting_id:int|None=None,skip:int=0,limit:int=100,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Task).filter_by(user_id=u.id)
    if search: q=q.filter(Task.title.ilike(f'%{search}%')|Task.description.ilike(f'%{search}%'))
    if status: q=q.filter_by(status=status)
    if priority: q=q.filter_by(priority=priority)
    if owner: q=q.filter(Task.owner.ilike(f'%{owner}%'))
    if meeting_id: q=q.filter_by(meeting_id=meeting_id)
    return {'items':[task_json(t) for t in q.order_by(Task.created_at.desc()).offset(skip).limit(min(limit,200)).all()],'total':q.count()}
@app.post('/api/tasks')
def create_task(b:TaskInput,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if b.meeting_id: owned_meeting(db,u.id,b.meeting_id)
    t=Task(user_id=u.id,**b.model_dump()); db.add(t); db.commit(); db.refresh(t); return task_json(t)
def owned_task(db,uid,tid):
    t=db.query(Task).filter_by(id=tid,user_id=uid).first()
    if not t: raise HTTPException(404,'Task not found')
    return t
@app.get('/api/tasks/{tid}')
def get_task(tid:int,db:Session=Depends(get_db),u:User=Depends(current_user)): return task_json(owned_task(db,u.id,tid))
@app.patch('/api/tasks/{tid}')
def patch_task(tid:int,b:TaskPatch,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=owned_task(db,u.id,tid)
    for k,v in b.model_dump(exclude_unset=True).items(): setattr(t,k,v)
    db.commit(); db.refresh(t); return task_json(t)
@app.delete('/api/tasks/{tid}')
def delete_task(tid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    db.delete(owned_task(db,u.id,tid)); db.commit(); return {'ok':True}
@app.post('/api/tasks/{tid}/approve')
def approve_task(tid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=owned_task(db,u.id,tid); t.status='pending'; db.commit(); return task_json(t)
@app.post('/api/tasks/{tid}/reject')
def reject_task(tid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    db.delete(owned_task(db,u.id,tid)); db.commit(); return {'ok':True}
@app.get('/api/decisions')
def decisions(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return {'items':[{'id':d.id,'title':d.title,'description':d.description,'evidence':d.evidence,'confidence':d.confidence,'meeting_id':d.meeting_id,'meeting_title':d.meeting.title,'created_at':d.created_at} for d in db.query(Decision).filter_by(user_id=u.id).order_by(Decision.created_at.desc()).all()]}
@app.patch('/api/decisions/{did}')
def patch_decision(did:int,b:DecisionPatch,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.query(Decision).filter_by(id=did,user_id=u.id).first()
    if not d: raise HTTPException(404,'Decision not found')
    for k,v in b.model_dump(exclude_unset=True).items(): setattr(d,k,v)
    db.commit(); return {'ok':True}
@app.delete('/api/decisions/{did}')
def delete_decision(did:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.query(Decision).filter_by(id=did,user_id=u.id).first()
    if not d: raise HTTPException(404,'Decision not found')
    db.delete(d); db.commit(); return {'ok':True}
@app.get('/api/risks')
def risks(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return {'items':[{'id':r.id,'description':r.description,'severity':r.severity,'suggested_resolution':r.suggested_resolution,'evidence':r.evidence,'status':r.status,'note':r.note,'meeting_id':r.meeting_id,'meeting_title':r.meeting.title} for r in db.query(Risk).filter_by(user_id=u.id).all()]}
@app.patch('/api/risks/{rid}')
def patch_risk(rid:int,b:RiskPatch,db:Session=Depends(get_db),u:User=Depends(current_user)):
    r=db.query(Risk).filter_by(id=rid,user_id=u.id).first()
    if not r: raise HTTPException(404,'Risk not found')
    for k,v in b.model_dump(exclude_unset=True).items(): setattr(r,k,v)
    db.commit(); return {'ok':True}
@app.delete('/api/risks/{rid}')
def delete_risk(rid:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    r=db.query(Risk).filter_by(id=rid,user_id=u.id).first()
    if not r: raise HTTPException(404,'Risk not found')
    db.delete(r); db.commit(); return {'ok':True}
@app.get('/api/dashboard/stats')
def stats(db:Session=Depends(get_db),u:User=Depends(current_user)):
    ts=db.query(Task).filter_by(user_id=u.id).all(); today=date.today()
    return {'meetings':db.query(Meeting).filter_by(user_id=u.id).count(),'tasks':len(ts),'pending':sum(t.status in ('pending','in_progress','needs_review') for t in ts),'completed':sum(t.status=='completed' for t in ts),'overdue':sum(t.due_date is not None and t.due_date<today and t.status!='completed' for t in ts),'needs_review':sum(t.status=='needs_review' for t in ts),'completion_rate':round(100*sum(t.status=='completed' for t in ts)/len(ts)) if ts else 0}
@app.get('/api/dashboard/charts')
def charts(db:Session=Depends(get_db),u:User=Depends(current_user)):
    tasks=db.query(Task).filter_by(user_id=u.id).all(); grouped={k:sum(t.status==k for t in tasks) for k in ['needs_review','pending','in_progress','completed','blocked']}
    return {'status_distribution':[{'name':k.replace('_',' ').title(),'value':v} for k,v in grouped.items()],'weekly':[{'name':(date.today()-timedelta(days=6-i)).strftime('%a'),'created':sum((datetime.utcnow()-t.created_at).days==6-i for t in tasks)} for i in range(7)]}
@app.get('/api/dashboard/activity')
def activity(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return {'items':[{'type':'meeting','title':m.title,'date':m.created_at,'status':m.status} for m in db.query(Meeting).filter_by(user_id=u.id).order_by(Meeting.created_at.desc()).limit(8).all()]}
@app.get('/api/settings')
def settings_get(u:User=Depends(current_user)): return {'name':u.name,'email':u.email,'ai_provider':settings.ai_provider,'model':settings.ai_model if settings.ai_provider!='ollama' else settings.ollama_model,'api_key_configured':bool(settings.ai_api_key),'max_upload_mb':settings.max_upload_mb}
@app.patch('/api/settings')
def settings_patch(u:User=Depends(current_user)): return {'message':'AI settings are managed in backend/.env. Restart the API after changing provider configuration.'}

import json
from app.core.config import settings
from app.schemas import Extraction

def extract(transcript: str, meeting_date=None) -> tuple[Extraction,str]:
    mode=settings.ai_provider.lower()
    if mode=='mock':
        clean=' '.join(transcript.split())
        sentences=[s.strip() for s in clean.replace('!','.').replace('?','.').split('.') if len(s.strip())>25]
        points=[{'text':s[:180], 'evidence':s[:240]} for s in sentences[:4]]
        tasks=[]
        for s in sentences:
            low=s.lower()
            if any(k in low for k in (' will ','todo','action item','follow up','follow-up','need to ',' should ',' owner:')):
                tasks.append({'title':s[:180], 'description':'', 'owner':None,'due_date':None,'priority':'medium','evidence':s[:300],'confidence':0.58})
        decisions=[]
        for s in sentences:
            if any(k in s.lower() for k in ('decided','decision','agreed','approved')):
                decisions.append({'title':s[:150], 'description':s,'evidence':s[:300],'confidence':0.62})
        risks=[]
        for s in sentences:
            if any(k in s.lower() for k in ('risk','blocked','blocker','delay','concern','issue')):
                risks.append({'description':s,'severity':'medium','suggested_resolution':None,'evidence':s[:300],'confidence':0.55})
        result=Extraction(summary=(clean[:500] + ('…' if len(clean)>500 else '')) or 'No transcript text was found.',key_points=points,decisions=decisions,action_items=tasks,risks_and_blockers=risks,open_questions=[])
        return result,'mock'
    if mode in ('openai','openai_compatible','ollama'):
        import httpx
        if len(transcript) > 100000:
            raise ValueError('Transcript exceeds the current AI extraction limit of 100,000 characters. The full transcript is preserved; split the source into shorter meeting sections and retry.')
        base=settings.ollama_base_url if mode=='ollama' else settings.ai_base_url
        model=settings.ollama_model if mode=='ollama' else settings.ai_model
        if not base or not model: raise ValueError('Configure AI_BASE_URL and AI_MODEL (or OLLAMA_MODEL) in backend/.env.')
        prompt='Extract meeting summary, key_points (text/evidence), decisions (title/description/evidence/confidence), action_items (title/description/owner/due_date/priority/evidence/confidence), risks_and_blockers (description/severity/suggested_resolution/evidence/confidence), and open_questions (question/evidence). Never infer unknown owners or dates. Return JSON only. Transcript:\n'+transcript
        headers={'Authorization':f'Bearer {settings.ai_api_key}'} if settings.ai_api_key and mode!='ollama' else {}
        response=httpx.post(base.rstrip('/')+'/v1/chat/completions',headers=headers,json={'model':model,'messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'}},timeout=90)
        response.raise_for_status(); payload=response.json()['choices'][0]['message']['content']; return Extraction.model_validate(json.loads(payload)),mode
    raise ValueError(f'Unknown AI_PROVIDER "{settings.ai_provider}".')

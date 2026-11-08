from datetime import timedelta
from fastapi import APIRouter,Depends,HTTPException
from core import current_user,stamp,now,Document
from research_models import ResearchAction
from research_core import get_research,change_request,visible_research,is_paid,require_owner,require_worker

router=APIRouter(tags=['research workflow'])

@router.post('/research/{rid}/action',response_model=Document)
async def research_action(rid:str,data:ResearchAction,user=Depends(current_user)):
    row=await get_research(rid);action=data.action;note=data.note.strip();updates={}
    if action=='claim':
        if user['role']!='employee':raise HTTPException(403,'الاستلام متاح للموظفين فقط')
        if row['status']!='available' or row['assigned_to'] or not row.get('accepted_quote') or row.get('cancel_requested'):raise HTTPException(409,'الطلب غير متاح؛ قد يكون استلمه موظف آخر أو طُلب إلغاؤه')
        updates={'assigned_to':user['id'],'status':'claimed','ever_claimed':True,'claimed_at':stamp(),'due_at':(now()+timedelta(days=row['accepted_quote']['delivery_days'])).isoformat()}
    elif action in ('return','start','deliver'):
        require_worker(row,user)
        if action=='return':
            if row['status'] not in ('claimed','in_progress','revision_requested'):raise HTTPException(409,'لا يمكن إعادة الطلب بعد تسليمه')
            if not note:raise HTTPException(422,'وضح سبب إعادة الطلب')
            updates={'assigned_to':None,'status':'available','due_at':None}
        elif action=='start':
            if row['status'] not in ('claimed','revision_requested'):raise HTTPException(409,'بدأت معالجة هذا الطلب بالفعل')
            updates={'status':'in_progress'}
        else:
            if row['status'] not in ('claimed','in_progress','revision_requested'):raise HTTPException(409,'الطلب ليس في مرحلة قابلة للتسليم')
            if not any(f['revision']==row['revision_count'] for f in row['result_files']):raise HTTPException(422,'ارفع ملف النتائج لهذه الجولة أولًا')
            updates={'released_file_ids':[f['id'] for f in row['result_files']],'status':'delivered' if is_paid(row) else 'ready_payment','delivered_at':stamp() if is_paid(row) else None}
    elif action in ('revision','complete','cancel'):
        require_owner(row,user)
        if action=='revision':
            if row['status']!='delivered' or not is_paid(row):raise HTTPException(409,'طلب التعديل متاح بعد تسليم النتائج واعتماد السداد')
            if row['revision_count']>=1:raise HTTPException(409,'استُخدمت جولة التعديل المتفق عليها؛ التوسعات تتطلب طلبًا جديدًا')
            if not note:raise HTTPException(422,'وضح التعديل المطلوب ضمن النطاق المتفق عليه')
            updates={'status':'revision_requested','revision_count':row['revision_count']+1,'revision_note':note}
        elif action=='complete':
            if row['status']!='delivered' or not is_paid(row):raise HTTPException(409,'يمكن اعتماد الإكمال بعد تسليم النتائج والسداد')
            updates={'status':'completed','completed_at':stamp(),'cancel_requested':False}
        else:
            if row['status'] in ('cancelled','completed'):raise HTTPException(409,'الطلب مغلق بالفعل')
            if row.get('cancel_requested'):raise HTTPException(409,'طلب الإلغاء قيد المراجعة بالفعل')
            if not note:raise HTTPException(422,'يرجى توضيح سبب الإلغاء')
            if not row['ever_claimed'] and not row['paid_minor'] and row['payment_status']!='pending':updates={'status':'cancelled','assigned_to':None}
            else:updates={'cancel_requested':True,'cancel_note':note}
    elif action=='reopen_assignment':
        if user['role']!='admin':raise HTTPException(403,'إعادة الإسناد متاحة للإدارة فقط')
        if row['status'] not in ('claimed','in_progress','revision_requested') or not row.get('assigned_to'):raise HTTPException(409,'الطلب غير مسند لموظف قيد المعالجة')
        if not note:raise HTTPException(422,'حدد سبب إعادة الإسناد')
        updates={'assigned_to':None,'status':'available','due_at':None}
    else:
        if user['role']!='admin':raise HTTPException(403,'مراجعة الإلغاء متاحة للإدارة فقط')
        if not row.get('cancel_requested') or row['status'] in ('completed','cancelled'):raise HTTPException(409,'لا يوجد طلب إلغاء معلق')
        if not note:raise HTTPException(422,'وضح قرار الإلغاء وأي تسوية مالية خارج المنصة')
        updates={'cancel_requested':False,'cancellation_resolution':note}
        if action=='approve_cancel':updates.update(status='cancelled',assigned_to=None)
    updated=await change_request(row,user,updates,action,note,financial=action in ('cancel','approve_cancel','reject_cancel'))
    return await visible_research(updated,user) if action!='return' else {'success':True,'id':rid,'status':'available'}
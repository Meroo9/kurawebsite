from fastapi import APIRouter,Depends,HTTPException,Query
from core import db,uid,stamp,current_user,admin_user,Document
from research_models import ResearchReceipt,ResearchReceiptReview,minor_amount
from research_core import get_research,require_owner,change_request,visible_research,is_paid

router=APIRouter(tags=['research payments'])

@router.post('/research/{rid}/receipts',response_model=Document)
async def receipt(rid:str,data:ResearchReceipt,user=Depends(current_user)):
    row=await get_research(rid);require_owner(row,user)
    if not row.get('accepted_quote') or row['status']=='cancelled' or is_paid(row) or row['payment_status']=='pending':raise HTTPException(409,'لا يمكن إرسال إيصال في هذه الحالة')
    file=await db.files.find_one({'id':data.file_id,'purpose':'research_receipt','owner_id':user['id'],'context_id':rid,'is_deleted':False},{'_id':0})
    if not file:raise HTTPException(422,'أرفق إيصالًا صالحًا لهذا الطلب')
    if any(r['file_id']==data.file_id for r in row['receipts']):raise HTTPException(409,'أرسل إيصالًا جديدًا بدل الإيصال السابق')
    amount=minor_amount(data.amount)
    if amount>row['accepted_quote']['amount_minor']-row['paid_minor']:raise HTTPException(422,'المبلغ يتجاوز المتبقي للطلب')
    item={'id':uid(),'file_id':file['id'],'amount_minor':amount,'status':'pending','reason':'','submitted_at':stamp()}
    updated=await change_request(row,user,{'payment_status':'pending','receipts':[*row['receipts'],item]},'receipt_submitted',financial=True)
    return await visible_research(updated,user)

@router.post('/research/{rid}/review-receipt',response_model=Document)
async def review(rid:str,data:ResearchReceiptReview,user=Depends(admin_user)):
    row=await get_research(rid)
    if row['status']=='cancelled':raise HTTPException(409,'الطلب ملغى؛ وثّق التسوية خارج المنصة')
    item=next((r for r in row['receipts'] if r['id']==data.receipt_id and r['status']=='pending'),None)
    if not item or row['payment_status']!='pending':raise HTTPException(409,'هذا الإيصال ليس قيد المراجعة')
    if data.decision=='rejected' and not data.reason.strip():raise HTTPException(422,'سبب رفض الإيصال مطلوب')
    updated_item={**item,'status':data.decision,'reason':data.reason.strip(),'reviewed_at':stamp(),'reviewer_id':user['id']}
    paid=row['paid_minor']+(item['amount_minor'] if data.decision=='approved' else 0)
    if paid>row['accepted_quote']['amount_minor']:raise HTTPException(409,'المبلغ المعتمد يتجاوز قيمة الطلب')
    fully=paid>=row['accepted_quote']['amount_minor']
    updates={'receipts':[updated_item if r['id']==item['id'] else r for r in row['receipts']],'paid_minor':paid,'payment_status':'paid' if fully else ('partial' if paid else ('rejected' if data.decision=='rejected' else 'unpaid'))}
    if fully and row['status']=='ready_payment':updates.update(status='delivered',delivered_at=stamp())
    return await visible_research(await change_request(row,user,updates,'receipt_'+data.decision,data.reason.strip(),True),user)

@router.get('/my/research-payments',response_model=Document)
async def research_payments(page:int=Query(1,ge=1),user=Depends(current_user)):
    where={'owner_id':user['id'],'accepted_quote':{'$ne':None}}
    rows=await db.research_requests.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*15).limit(15).to_list(15)
    totals=await db.research_requests.aggregate([{'$match':where},{'$group':{'_id':'$accepted_quote.currency','paid':{'$sum':'$paid_minor'},'remaining':{'$sum':{'$cond':[{'$eq':['$status','cancelled']},0,{'$subtract':['$accepted_quote.amount_minor','$paid_minor']}]}}}}]).to_list(100)
    return {'items':[{'id':r['id'],'title':r['title'],'reference':r['reference'],'amount_minor':r['accepted_quote']['amount_minor'],'currency':r['accepted_quote']['currency'],'paid_minor':r['paid_minor'],'remaining_minor':max(0,r['accepted_quote']['amount_minor']-r['paid_minor']),'status':r['status'],'payment_status':r['payment_status'],'created_at':r['created_at'],'settlement_required':r['status']=='cancelled'} for r in rows],'total':await db.research_requests.count_documents(where),'page':page,'balances':[{'currency':t['_id'],'paid_minor':t['paid'],'remaining_minor':t['remaining']} for t in totals]}
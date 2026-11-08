import re
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,ConfigDict
from pymongo.errors import DuplicateKeyError
from core import db,uid,stamp,current_user,optional_user,admin_user,audit,limit,Document

router=APIRouter(tags=['posts'])

class PostInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    title:str=Field(min_length=3,max_length=180)
    body:str=Field(min_length=10,max_length=10000)
    image_id:str|None=None
    published:bool=True

class CommentInput(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    body:str=Field(min_length=1,max_length=1500)

class ReactionInput(BaseModel):
    liked:bool

async def get_post(pid,user=None):
    where={'id':pid,'deleted':False}
    if not user or user.get('role')!='admin' or user.get('status')!='active':where['published']=True
    post=await db.posts.find_one(where,{'_id':0})
    if not post:raise HTTPException(404,'المنشور غير متاح')
    return post

async def present_post(post,user=None):
    post={k:v for k,v in post.items() if k not in ('_id','author_id')}
    post['like_count']=await db.post_reactions.count_documents({'post_id':post['id']})
    post['comment_count']=await db.post_comments.count_documents({'post_id':post['id'],'deleted':False})
    post['liked']=bool(user and await db.post_reactions.count_documents({'post_id':post['id'],'user_id':user['id']}))
    post['author_name']='مركز كورا للأبحاث'
    return post

@router.get('/posts',response_model=Document)
async def posts(q:str='',page:int=Query(1,ge=1),user=Depends(optional_user)):
    where={'deleted':False,'published':True}
    if q:where['$or']=[{k:{'$regex':re.escape(q[:100]),'$options':'i'}} for k in ('title','body')]
    items=await db.posts.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*6).limit(6).to_list(6)
    return {'items':[await present_post(p,user) for p in items],'total':await db.posts.count_documents(where),'page':page}

@router.get('/posts/{pid}',response_model=Document)
async def post_detail(pid:str,user=Depends(optional_user)):
    return await present_post(await get_post(pid,user),user)

async def validate_image(image_id):
    if image_id and not await db.files.find_one({'id':image_id,'purpose':'post_image','is_deleted':False},{'_id':0,'id':1}):raise HTTPException(422,'صورة المنشور غير صحيحة')

@router.get('/admin/posts',response_model=Document)
async def admin_posts(q:str='',status:str='',page:int=Query(1,ge=1),user=Depends(admin_user)):
    where={'deleted':False}
    if q:where['title']={'$regex':re.escape(q[:100]),'$options':'i'}
    if status in ('published','draft'):where['published']=status=='published'
    items=await db.posts.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*12).limit(12).to_list(12)
    return {'items':[await present_post(p,user) for p in items],'total':await db.posts.count_documents(where),'page':page}

@router.post('/admin/posts',response_model=Document)
async def create_post(data:PostInput,user=Depends(admin_user)):
    await validate_image(data.image_id)
    post={**data.model_dump(),'id':uid(),'author_id':user['id'],'created_at':stamp(),'updated_at':stamp(),'deleted':False}
    await db.posts.insert_one(post.copy());await audit(user['id'],'post_created',post['id'])
    return await present_post(post,user)

@router.put('/admin/posts/{pid}',response_model=Document)
async def update_post(pid:str,data:PostInput,user=Depends(admin_user)):
    await get_post(pid,user);await validate_image(data.image_id)
    await db.posts.update_one({'id':pid,'deleted':False},{'$set':{**data.model_dump(),'updated_at':stamp()}})
    await audit(user['id'],'post_updated',pid)
    return await present_post(await get_post(pid,user),user)

@router.delete('/admin/posts/{pid}')
async def delete_post(pid:str,user=Depends(admin_user)):
    result=await db.posts.update_one({'id':pid,'deleted':False},{'$set':{'deleted':True,'published':False,'updated_at':stamp()}})
    if not result.modified_count:raise HTTPException(404,'المنشور غير موجود')
    await audit(user['id'],'post_deleted',pid)
    return {'success':True}

@router.put('/posts/{pid}/reaction',response_model=Document)
async def reaction(pid:str,data:ReactionInput,user=Depends(current_user)):
    post=await get_post(pid)
    where={'post_id':pid,'user_id':user['id']}
    if data.liked:
        try:await db.post_reactions.update_one(where,{'$setOnInsert':{**where,'id':uid(),'created_at':stamp()}},upsert=True)
        except DuplicateKeyError:pass
    else:await db.post_reactions.delete_one(where)
    return await present_post(post,user)

@router.get('/posts/{pid}/comments',response_model=Document)
async def comments(pid:str,page:int=Query(1,ge=1),user=Depends(optional_user)):
    await get_post(pid,user)
    where={'post_id':pid,'deleted':False}
    items=await db.post_comments.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*15).limit(15).to_list(15)
    result=[]
    for item in items:
        author=await db.users.find_one({'id':item['user_id']},{'_id':0,'name':1})
        result.append({'id':item['id'],'body':item['body'],'created_at':item['created_at'],'author_name':author['name'] if author else 'عضو كورا','can_delete':bool(user and user.get('status')=='active' and (user['role']=='admin' or user['id']==item['user_id']))})
    return {'items':result,'total':await db.post_comments.count_documents(where),'page':page}

@router.post('/posts/{pid}/comments',response_model=Document)
async def add_comment(pid:str,data:CommentInput,request:Request,user=Depends(current_user)):
    await get_post(pid);await limit(request,'post-comments',40)
    item={'id':uid(),'post_id':pid,'user_id':user['id'],'body':data.body,'created_at':stamp(),'deleted':False}
    await db.post_comments.insert_one(item.copy())
    return {'id':item['id'],'body':item['body'],'created_at':item['created_at'],'author_name':user['name'],'can_delete':True}

@router.delete('/posts/{pid}/comments/{cid}')
async def delete_comment(pid:str,cid:str,user=Depends(current_user)):
    await get_post(pid,user)
    where={'id':cid,'post_id':pid,'deleted':False}
    if user['role']!='admin':where['user_id']=user['id']
    result=await db.post_comments.update_one(where,{'$set':{'deleted':True}})
    if not result.modified_count:raise HTTPException(404,'التعليق غير موجود أو لا تملك صلاحية حذفه')
    await audit(user['id'],'comment_deleted',cid)
    return {'success':True}

@router.get('/post-images/{fid}')
async def public_post_image(fid:str):
    from media import storage_download,stream_spool
    if not await db.posts.find_one({'image_id':fid,'published':True,'deleted':False},{'_id':0,'id':1}):raise HTTPException(404,'الصورة غير متاحة')
    image=await db.files.find_one({'id':fid,'purpose':'post_image','is_deleted':False},{'_id':0})
    if not image:raise HTTPException(404,'الصورة غير متاحة')
    spool,size=await storage_download(image['storage_path'])
    if not await db.posts.find_one({'image_id':fid,'published':True,'deleted':False},{'_id':0,'id':1}):
        spool.close();raise HTTPException(404,'الصورة غير متاحة')
    return StreamingResponse(stream_spool(spool,size),media_type=image['content_type'],headers={'Content-Length':str(size)})
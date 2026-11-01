import {useEffect,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {Plus,Save,Loader2} from 'lucide-react';
import {toast} from 'sonner';
import {api,message,date,fileUrl} from '../../lib/api';
import {PageHeading,Field,SelectField,Btn,Busy,Status,Empty,Pager,ErrorNotice} from '../../components/Shared';
import {Dialog,DialogContent,DialogTitle,DialogDescription} from '../../components/ui/dialog';
import {KrcCorrection} from './KrcCorrection';

export default function AdminUsers(){
 const [params]=useSearchParams();
 const [data,setData]=useState(null),[q,setQ]=useState(''),[role,setRole]=useState(''),[status,setStatus]=useState(''),[studentStatus,setStudentStatus]=useState(params.get('student_status')||''),[page,setPage]=useState(1),[selected,setSelected]=useState(null),[creating,setCreating]=useState(false),[error,setError]=useState('');
 const load=()=>api.get('/admin/users',{params:{q,role,status,student_status:studentStatus,page}}).then(r=>setData(r.data)).catch(e=>setError(message(e)));
 useEffect(()=>{load();},[q,role,status,studentStatus,page]);
 const close=()=>{setSelected(null);setCreating(false);};
 const done=()=>{close();load();};
 return <>
  <PageHeading eyebrow="إدارة الحسابات" title="المستخدمون" text="اعتماد الطلاب، وإدارة الموظفين وصلاحيات الوصول."><Btn data-testid="create-employee" onClick={()=>setCreating(true)}><Plus size={18}/>إضافة موظف</Btn></PageHeading>
  <div className="filter-row">
   <Field id="users-search" label="البحث" placeholder="الاسم، البريد، الهاتف أو KRC" value={q} onChange={e=>{setQ(e.target.value);setPage(1);}}/>
   <SelectField id="users-role" label="الدور" value={role} onChange={e=>{setRole(e.target.value);setPage(1);}}><option value="">جميع الأدوار</option><option value="student">طالب كورا</option><option value="visitor">زائر مسجل</option><option value="employee">موظف</option><option value="admin">مدير</option></SelectField>
   <SelectField id="users-status" label="الحالة" value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="">جميع الحالات</option><option value="active">نشط</option><option value="blocked">محظور</option><option value="inactive">غير نشط</option></SelectField>
   <SelectField id="users-student-status" label="اعتماد KRC" value={studentStatus} onChange={e=>{setStudentStatus(e.target.value);setPage(1);}}><option value="">الكل</option><option value="pending">قيد المراجعة</option><option value="approved">معتمد</option><option value="rejected">مرفوض</option></SelectField>
  </div><ErrorNotice text={error}/>
  {!data&&!error?<Busy/>:data?.items.length?<><div className="table-scroll"><table><thead><tr><th>المستخدم</th><th>الدور</th><th>حالة الحساب</th><th>رقم كورا</th><th>الإجراءات</th></tr></thead><tbody>{data.items.map(u=><tr key={u.id} data-testid={`user-row-${u.id}`}><td><strong>{u.name}</strong><small dir="ltr">{u.email}</small></td><td><Status value={u.role} id={`user-role-${u.id}`}/></td><td><Status value={u.status} id={`user-status-${u.id}`}/></td><td><span dir="ltr">{u.krc||'—'}</span>{u.krc&&<Status value={u.student_status} id={`student-status-${u.id}`}/>}</td><td><Btn data-testid={`edit-user-${u.id}`} variant="outline" onClick={()=>setSelected(u)}>التفاصيل</Btn></td></tr>)}</tbody></table></div><Pager page={page} total={data.total} onChange={setPage}/></>:<Empty title="لا يوجد مستخدمون مطابقون"/>}
  <Dialog open={!!selected||creating} onOpenChange={open=>{if(!open)close();}}><DialogContent className="k-modal" data-testid="user-editor"><DialogTitle>{creating?'إضافة موظف':'تفاصيل المستخدم'}</DialogTitle><DialogDescription>بيانات الحساب والصلاحيات المعتمدة.</DialogDescription>{(selected||creating)&&<AccountEditor user={selected} creating={creating} onDone={done}/>}</DialogContent></Dialog>
 </>;
}

const AccountEditor=({user,creating,onDone})=>{
 const [data,setData]=useState({name:user?.name||'',email:user?.email||'',phone:user?.phone||'',password:'',status:user?.status||'active'}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const change=(key,value)=>setData(d=>({...d,[key]:value}));
 const save=async e=>{e.preventDefault();setBusy(true);try{
  if(creating)await api.post('/admin/employees',{...data,is_student:false});
  else await api.patch(`/admin/users/${user.id}`,{name:data.name,email:data.email,phone:data.phone,status:data.status});
  toast.success('تم حفظ الحساب');onDone();
 }catch(e){setError(message(e));}finally{setBusy(false);}};
 const decide=async decision=>{setBusy(true);try{await api.patch(`/admin/users/${user.id}`,{student_decision:decision});toast.success('تم تحديث اعتماد الطالب');onDone();}catch(e){setError(message(e));}finally{setBusy(false);}};
 return <form className="form-stack" onSubmit={save}>
  {user?.avatar_id&&<img className="profile-avatar" src={fileUrl(user.avatar_id)} alt="الصورة الشخصية"/>}
  <Field id="edit-user-name" label="الاسم الكامل" required value={data.name} onChange={e=>change('name',e.target.value)}/>
  <Field id="edit-user-email" label="البريد الإلكتروني" type="email" required dir="ltr" value={data.email} onChange={e=>change('email',e.target.value)}/>
  <Field id="edit-user-phone" label="الهاتف" required dir="ltr" value={data.phone} onChange={e=>change('phone',e.target.value)}/>
  {creating?<Field id="employee-password" label="كلمة المرور الأولية" type="password" minLength={10} required value={data.password} onChange={e=>change('password',e.target.value)}/>:<SelectField id="edit-user-status" label="حالة الحساب" disabled={user.role==='admin'} value={data.status} onChange={e=>change('status',e.target.value)}><option value="active">نشط</option><option value="blocked">محظور</option><option value="inactive">غير نشط</option></SelectField>}
  {user?.krc&&<div className="user-student-details" data-testid="student-details"><h3>بيانات طالب كورا</h3><p>رقم كورا: <b dir="ltr">{user.krc}</b></p><p>الجامعة: {user.university}</p><p>المجال: {user.research_field}</p><p>تاريخ التسجيل: {date(user.registration_date)}</p><Status value={user.student_status} id="editing-student-status"/>{['visitor','student'].includes(user.role)&&<div className="row"><Btn data-testid="approve-student" type="button" disabled={busy} onClick={()=>decide('approved')}>اعتماد الطالب</Btn><Btn data-testid="reject-student" type="button" variant="outline" disabled={busy} onClick={()=>decide('rejected')}>رفض الاعتماد</Btn></div>}<KrcCorrection user={user} onDone={onDone}/></div>}
  <ErrorNotice text={error}/><Btn data-testid="save-user" type="submit" disabled={busy}>{busy?<Loader2 className="spin" size={17}/>:<Save size={17}/>}حفظ الحساب</Btn>
 </form>;
};
import {useEffect,useState} from 'react';
import {Link,useNavigate,useParams} from 'react-router-dom';
import {ArrowLeft,BookOpen,LockKeyhole,Play,Download,CheckCircle,Loader2,ChevronLeft} from 'lucide-react';
import {toast} from 'sonner';
import {api,message,money,fileUrl} from '../lib/api';
import {useApp} from '../context/AppContext';
import {Busy,Btn,Status,ErrorNotice} from '../components/Shared';
import {ReceiptForm,ReceiptHistory} from './Courses';

export default function CourseDetail(){
 const {id}=useParams(),{user}=useApp(),navigate=useNavigate();
 const [course,setCourse]=useState(null),[purchase,setPurchase]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[viewer,setViewer]=useState(null);
 useEffect(()=>{
  let alive=true;setViewer(null);setPurchase(null);setError('');
  api.get(`/courses/${id}`).then(r=>{if(alive)setCourse(r.data);}).catch(e=>{if(alive)setError(message(e));});
  if(user)api.get(`/my/purchases/course/${id}`).then(r=>{if(alive)setPurchase(r.data.purchase);}).catch(()=>{});
  return()=>{alive=false;};
 },[id,user]);
 const buy=async()=>{if(!user){navigate('/login',{state:{from:`/courses/${id}`}});return;}setBusy(true);try{setPurchase((await api.post(`/courses/${id}/purchase`)).data);}catch(e){toast.error(message(e));}finally{setBusy(false);}};
 if(error)return <div className="container section-pad"><ErrorNotice text={error}/></div>;
 if(!course)return <Busy/>;
 return <div className="container course-detail">
  <Link data-testid="back-to-courses" className="breadcrumb" to="/courses">الكورسات والمحاضرات<ChevronLeft size={15}/>{course.title}</Link>
  <div className="course-detail-grid"><div>
   <span className="eyebrow">كورسات كورا</span><h1 data-testid="course-detail-title">{course.title}</h1>
   <p className="course-description" data-testid="course-detail-description">{course.description}</p>
   <div className="course-facts"><span><BookOpen size={18}/>{course.lectures.length} محاضرة</span><span><CheckCircle size={18}/>وصول غير محدد المدة</span><span><Download size={18}/>مواد قابلة للتنزيل</span></div>
   <section className="lecture-section"><h2>محتوى الكورس</h2>{course.lectures.length?course.lectures.map((l,i)=><div className="lecture-row" key={l.id} data-testid={`lecture-${l.id}`}><span className="lecture-index">{String(i+1).padStart(2,'0')}</span><div><strong>{l.title}</strong>{l.description&&<p>{l.description}</p>}</div>{course.has_access?<div className="row"><Btn data-testid={`view-lecture-${l.id}`} variant="outline" onClick={()=>setViewer(l)}><Play size={16}/>عرض</Btn><a data-testid={`download-lecture-${l.id}`} className="icon-button" aria-label={`تنزيل ${l.title}`} title="تنزيل" href={fileUrl(l.file_id,true)}><Download size={19}/></a></div>:<LockKeyhole size={18} className="muted"/>}</div>):<p className="notice" data-testid="no-lectures">لم تُضف محاضرات لهذا الكورس بعد.</p>}</section>
   {viewer&&<div className="lecture-viewer" data-testid="lecture-viewer"><div className="row"><h2>{viewer.title}</h2><Btn variant="ghost" data-testid="close-lecture-viewer" onClick={()=>setViewer(null)}>إغلاق</Btn></div><LecturePreview key={viewer.file_id} fileId={viewer.file_id}/><a data-testid="viewer-download" href={fileUrl(viewer.file_id,true)} className="text-link"><Download size={18}/>تنزيل الملف</a></div>}
  </div><aside className="purchase-panel"><div className="purchase-icon"><BookOpen size={36}/></div>
   {course.has_access?<div className="access-granted" data-testid="course-access-granted"><CheckCircle/><strong>هذا الكورس متاح لك</strong><p>رحلة معرفية موفّقة!</p></div>:<><span>سعر الكورس كاملًا</span><strong className="course-price" data-testid="course-detail-price">{course.price_minor===0?'مجاني':money(course.price_minor,course.currency)}</strong>{course.free_for_students&&<div className="student-free" data-testid="student-free-label">مجاني لطلاب كورا المعتمدين</div>}<p>يشمل جميع محاضرات الكورس ومواده.</p>
   {purchase?<><Status value={purchase.status} id="purchase-status"/>{purchase.status==='pending'&&<p className="notice">وصل إيصالك، وهو الآن قيد المراجعة.</p>}{['awaiting_receipt','rejected'].includes(purchase.status)&&<ReceiptForm purchase={purchase} onDone={setPurchase}/>}<ReceiptHistory purchase={purchase}/></>:<Btn data-testid="course-purchase" onClick={buy} disabled={busy}>{busy?<Loader2 className="spin"/>:null}{!user&&course.price_minor===0?'سجّل الدخول لبدء التعلم':'طلب شراء الكورس'}<ArrowLeft size={17}/></Btn>}
   <div className="purchase-security"><LockKeyhole size={15}/>دفع خارجي وإيصال معتمد من الإدارة</div></>}
  </aside></div>
 </div>;
}

const LecturePreview=({fileId})=>{
 const [type,setType]=useState(''),[url,setUrl]=useState(''),[error,setError]=useState('');
 useEffect(()=>{let objectUrl,active=true;
  api.get(`/files/${fileId}/metadata`).then(async meta=>{
   if(!active)return;
   setType(meta.data.content_type);
   if(meta.data.content_type.startsWith('video/')){setUrl(fileUrl(fileId));return;}
   if(!['application/pdf','text/plain'].includes(meta.data.content_type)&&!meta.data.content_type.startsWith('image/')){setUrl('download-only');return;}
   const r=await api.get(`/files/${fileId}`,{responseType:'blob'});
   if(active){objectUrl=URL.createObjectURL(r.data);setUrl(objectUrl);}
  }).catch(()=>{if(active)setError('تعذر عرض الملف. قد تكون صلاحية الوصول تغيّرت.');});
  return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[fileId]);
 if(error)return <ErrorNotice text={error}/>;
 if(!url)return <Busy/>;
 if(type.startsWith('video/'))return <video data-testid="lecture-video" controls src={url} preload="metadata"/>;
 if(type.startsWith('image/'))return <img data-testid="lecture-image" src={url} alt="محتوى المحاضرة"/>;
 if(type.includes('pdf')||type.includes('text/plain'))return <iframe data-testid="lecture-document" title="محتوى المحاضرة" src={url}/>;
 return <p className="notice" data-testid="lecture-download-only">هذا النوع متاح للتنزيل وفتحه في البرنامج المناسب.</p>;
};
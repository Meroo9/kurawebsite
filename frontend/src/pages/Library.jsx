import {useState,useEffect} from 'react';
import {Link} from 'react-router-dom';
import {api,message} from '../lib/api';
import {useApp} from '../context/AppContext';
import {PageHeading,Field,SelectField,Btn,Busy,CourseCard,Empty,Pager,ErrorNotice} from '../components/Shared';
export default function Library(){
 const {categories}=useApp();
 const [data,setData]=useState(null),[q,setQ]=useState(''),[category,setCategory]=useState(''),[page,setPage]=useState(1),[error,setError]=useState('');
 useEffect(()=>{let active=true;api.get('/my/library',{params:{q,category,page}}).then(r=>{if(active)setData(r.data);}).catch(e=>{if(active)setError(message(e));});return()=>{active=false;};},[q,category,page]);
 return <><PageHeading eyebrow="تعلّم على إيقاعك" title="كورساتي" text="جميع الكورسات المتاحة لك في مساحة واحدة."/><div className="filter-row"><Field id="my-courses-search" label="البحث في كورساتي" value={q} onChange={e=>{setQ(e.target.value);setPage(1);}}/><SelectField id="my-courses-category" label="التصنيف" value={category} onChange={e=>{setCategory(e.target.value);setPage(1);}}><option value="">جميع التصنيفات</option>{categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</SelectField></div><ErrorNotice text={error}/>{!data&&!error?<Busy/>:data?.items.length?<><div className="courses-grid">{data.items.map(c=><CourseCard key={c.id} course={{...c,has_access:true}}/>)}</div><Pager size={12} page={page} total={data.total} onChange={setPage}/></>:<Empty title="لا توجد كورسات مطابقة" action={<Btn asChild data-testid="my-courses-browse"><Link to="/courses">استكشف الكورسات</Link></Btn>}/>}</>;
}
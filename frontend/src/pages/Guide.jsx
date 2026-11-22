import {useMemo} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {BookOpen,Search,Printer,Download,ArrowLeft,ShieldCheck,ArrowUp,X} from 'lucide-react';
import {Btn,Empty} from '../components/Shared';
import {Input} from '../components/ui/input';
import {Accordion,AccordionItem,AccordionTrigger,AccordionContent} from '../components/ui/accordion';
import guide from '../content/user-guide.ar.json';
import './Guide.css';

const normalize=value=>value.normalize('NFKD').replace(/[\u064b-\u065f\u0670]/g,'').replace(/[أإآ]/g,'ا').toLocaleLowerCase('ar');

export const GuideChapter=({chapter,index,print=false,searching=false})=>{
 const prefix=`guide-${print?'print':'screen'}-${chapter.id}`;
 return <section className="guide-chapter" id={print?`print-${chapter.id}`:`guide-${chapter.id}`} data-testid={prefix}>
  <header className="guide-chapter-heading"><span className="guide-chapter-number">{String(index+1).padStart(2,'0')}</span><div><small data-testid={`${prefix}-audience`}>{chapter.audience}</small><h2 data-testid={`${prefix}-title`}>{chapter.title}</h2></div></header>
  {chapter.intro&&<p className="guide-chapter-intro" data-testid={`${prefix}-intro`}>{chapter.intro}</p>}
  {chapter.steps&&<ol className="guide-steps">{chapter.steps.map((step,i)=><li key={i} data-testid={`${prefix}-step-${i}`}>{step}</li>)}</ol>}
  {chapter.table&&<div className="guide-table"><table data-testid={`${prefix}-table`}><thead><tr>{chapter.table.headers.map((text,i)=><th key={text} data-testid={`${prefix}-th-${i}`}>{text}</th>)}</tr></thead><tbody>{chapter.table.rows.map((row,i)=><tr key={i}>{row.map((text,j)=><td key={j} data-testid={`${prefix}-cell-${i}-${j}`}>{text}</td>)}</tr>)}</tbody></table></div>}
  {(chapter.notes||[]).map((note,i)=><div className="guide-note" key={i} data-testid={`${prefix}-note-${i}`}><ShieldCheck size={17}/><p>{note}</p></div>)}
  {chapter.questions&&(print||searching?<div className="guide-questions">{chapter.questions.map((item,i)=><div key={i}><h3 data-testid={`${prefix}-question-${i}`}>{item.question}</h3><p data-testid={`${prefix}-answer-${i}`}>{item.answer}</p></div>)}</div>:<Accordion type="multiple" className="guide-faq">{chapter.questions.map((item,i)=><AccordionItem value={`q-${i}`} key={i}><AccordionTrigger data-testid={`${prefix}-question-${i}`}>{item.question}</AccordionTrigger><AccordionContent data-testid={`${prefix}-answer-${i}`}>{item.answer}</AccordionContent></AccordionItem>)}</Accordion>)}
  {chapter.links?.length>0&&<div className="guide-chapter-links">{chapter.links.map((link,i)=>print?<span key={link.to}>{link.label}</span>:<Link data-testid={`${prefix}-link-${i}`} key={link.to} to={link.to}>{link.label}<ArrowLeft size={14}/></Link>)}</div>}
 </section>;
};

export default function Guide(){
 const [params,setParams]=useSearchParams();
 const role=guide.roles.some(r=>r.id===params.get('role'))?params.get('role'):'all';
 const query=params.get('q')||'';
 const chapters=useMemo(()=>guide.sections.filter(chapter=>(role==='all'||chapter.roles.includes(role))&&(!query.trim()||normalize(JSON.stringify(chapter)).includes(normalize(query.trim())))),[role,query]);
 const change=(key,value)=>{const next=new URLSearchParams(params);if(!value||value==='all')next.delete(key);else next.set(key,value);setParams(next,{replace:true});};
 return <div className="container guide-page" id="guide-top">
  <div className="guide-screen-content">
   <header className="guide-header"><div><span className="guide-eyebrow" data-testid="guide-eyebrow"><BookOpen size={17}/>مرجعك في كل خطوة</span><h1 data-testid="guide-title">دليل استخدام <em>كورا</em></h1><p data-testid="guide-subtitle">{guide.subtitle}</p></div><div className="guide-tools"><Btn variant="outline" data-testid="guide-print" onClick={()=>window.print()}><Printer size={17}/>طباعة / حفظ PDF</Btn><Btn variant="outline" asChild data-testid="guide-download"><a href="/docs/kura-user-guide-ar.md" download="kura-user-guide-ar.md"><Download size={17}/>تنزيل نسخة نصية</a></Btn></div></header>
   <div className="guide-controls"><div className="guide-role-tabs" role="group" aria-label="اختيار الدور">{guide.roles.map(item=><button key={item.id} className={item.id===role?'active':''} aria-pressed={item.id===role} data-testid={`guide-role-${item.id}`} onClick={()=>change('role',item.id)}>{item.label}</button>)}</div><div className="guide-search"><Search size={18}/><Input aria-label="البحث في الدليل" data-testid="guide-search" placeholder="ابحث عن إيصال، ملف، طلب…" value={query} maxLength={160} onChange={e=>change('q',e.target.value)}/>{query&&<button data-testid="guide-clear-search" title="مسح البحث" aria-label="مسح البحث" onClick={()=>change('q','')}><X size={15}/></button>}</div></div>
   <div className="guide-layout"><aside className="guide-sidebar"><div className="guide-contents-heading"><strong>في هذا الدليل</strong><span data-testid="guide-section-count">{chapters.length} فصلًا</span></div><nav aria-label="فصول الدليل">{chapters.map(chapter=><a data-testid={`guide-toc-${chapter.id}`} href={`#guide-${chapter.id}`} key={chapter.id}><span>{String(guide.sections.indexOf(chapter)+1).padStart(2,'0')}</span>{chapter.title}</a>)}</nav><div className="guide-scope"><ShieldCheck size={19}/><p data-testid="guide-scope">{guide.scope}</p></div><Link data-testid="guide-contact" className="text-link" to="/contact">تحتاج إلى مساعدة؟<ArrowLeft size={15}/></Link></aside><div className="guide-main">{chapters.length?chapters.map(chapter=><GuideChapter key={chapter.id} chapter={chapter} index={guide.sections.indexOf(chapter)} searching={!!query.trim()}/>):<Empty title="لا توجد نتائج مطابقة" text="جرّب كلمة أخرى أو اعرض الدليل كاملًا." action={<Btn variant="outline" data-testid="guide-reset-filters" onClick={()=>setParams({})}>إعادة ضبط البحث</Btn>}/>}<div className="guide-end"><span data-testid="guide-version">دليل كورا · الإصدار {guide.version}</span><a data-testid="guide-back-to-top" href="#guide-top">إلى بداية الدليل<ArrowUp size={15}/></a></div></div></div>
  </div>
  <div className="guide-print-content" aria-hidden="true" data-testid="guide-print-document"><header className="guide-print-header"><img src="/assets/kura-logo.webp" alt="كورا"/><div><h1>{guide.title}</h1><p>{guide.subtitle}</p><small>الإصدار {guide.version} · مركز كورا للأبحاث — KURA Research</small></div></header><p>{guide.scope}</p>{guide.sections.map((chapter,index)=><GuideChapter key={chapter.id} chapter={chapter} index={index} print/>)}</div>
 </div>;
}
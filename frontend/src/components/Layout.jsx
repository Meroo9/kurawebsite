import {useState} from 'react';
import {NavLink,Link,Outlet,useLocation,Navigate} from 'react-router-dom';
import {Menu,X,UserRound,UserRoundPlus,ArrowLeft,LogOut,BookOpen,LayoutDashboard,Wallet,Users,Receipt,Settings,FolderTree,ScrollText,ShieldCheck,Microscope,MessagesSquare} from 'lucide-react';
import {useApp} from '../context/AppContext';
import {Btn,Busy} from './Shared';
import {BookMarked} from 'lucide-react';
export const Logo=({footer=false})=><Link to="/" data-testid={footer?'footer-brand':'header-brand'} className="brand"><img src="/assets/kura-logo.webp" alt="شعار كورا"/><span><strong>مركز كورا للأبحاث</strong><small lang="en">KURA Research</small></span></Link>;
const publicLinks=[['/','الرئيسية'],['/about','عن كورا'],['/services','خدماتنا'],['/courses','المحاضرات'],['/pricing','الأسعار'],['/contact','اتصل بنا']];
const CommunityNav=({onNavigate})=> <><NavLink data-testid="nav-research" to="/research" onClick={onNavigate}>الطلبات البحثية</NavLink><NavLink data-testid="nav-posts" to="/posts" onClick={onNavigate}>المنشورات</NavLink></>;
export const PublicLayout=()=>{
 const [open,setOpen]=useState(false);const {user}=useApp();const location=useLocation();
 return <><header className="site-header"><div className="container header-inner"><Logo/><nav aria-label="القائمة الرئيسية" className={open?'main-nav open':'main-nav'}>{publicLinks.slice(0,4).map(([to,label])=><NavLink end={to==='/'} key={to} to={to} data-testid={`nav-${to==='/'?'home':to.slice(1)}`} onClick={()=>setOpen(false)}>{label}</NavLink>)}<CommunityNav onNavigate={()=>setOpen(false)}/>{publicLinks.slice(4).map(([to,label])=><NavLink key={to} to={to} data-testid={`nav-${to.slice(1)}`} onClick={()=>setOpen(false)}>{label}</NavLink>)}</nav><div className="header-actions">{user?<Btn asChild data-testid="open-workspace"><Link to={user.role==='admin'?'/admin':'/dashboard'}><LayoutDashboard size={17}/>مساحتي</Link></Btn>:<><Link className="login-link" data-testid="header-login" to="/login"><UserRound size={17}/>تسجيل الدخول</Link><Btn asChild data-testid="header-register"><Link to="/register">إنشاء حساب<UserRoundPlus size={17}/></Link></Btn></>}<button className="mobile-menu" aria-label={open?'إغلاق القائمة':'فتح القائمة'} data-testid="mobile-menu" onClick={()=>setOpen(!open)}>{open?<X/>:<Menu/>}</button></div></div></header><main key={location.pathname}><Outlet/></main><Footer/></>;
};
export const Footer=()=>{
 const {site}=useApp();
 return <footer className="footer"><div className="container footer-main"><div><Logo footer/><p data-testid="footer-tagline">علمٌ يبني المعرفة، ومعرفةٌ تصنع الأثر.</p></div>
  <div><h3>اكتشف كورا</h3><Link data-testid="footer-about" to="/about">عن المركز</Link><Link data-testid="footer-services" to="/services">خدماتنا</Link><Link data-testid="footer-courses" to="/courses">الكورسات والمحاضرات</Link></div>
  <div><h3>روابط تهمك</h3><Link data-testid="footer-guide" to="/guide">دليل الاستخدام</Link><Link data-testid="footer-account" to="/dashboard">حسابي</Link><Link data-testid="footer-contact" to="/contact">اتصل بنا</Link><Link data-testid="footer-privacy" to="/privacy">الخصوصية وحفظ الملفات</Link></div>
  {site?.contact_email&&<div><h3>تواصل معنا</h3><a data-testid="footer-email" href={`mailto:${site.contact_email}`}>{site.contact_email}</a></div>}
 </div><div className="container footer-bottom"><span data-testid="copyright">© {new Date().getFullYear()} مركز كورا للأبحاث. جميع الحقوق محفوظة.</span><span lang="en">LEARN. RESEARCH. MAKE AN IMPACT.</span></div></footer>;
};
export const Protected=({admin=false,children})=>{const {user,loading}=useApp();const loc=useLocation();if(loading)return <Busy/>;if(!user)return <Navigate to="/login" state={{from:loc.pathname}} replace/>;if(admin&&user.role!=='admin')return <Navigate to="/dashboard" replace/>;return children||<Outlet/>;};
const adminLinks=[['/admin','نظرة عامة',LayoutDashboard],['/admin/users','المستخدمون',Users],['/admin/courses','الكورسات والمحاضرات',BookOpen],['/admin/categories','التصنيفات',FolderTree],['/admin/purchases','إيصالات الكورسات',Receipt],['/admin/research','الطلبات البحثية',Microscope],['/admin/posts','المنشورات',MessagesSquare],['/admin/audit','سجل العمليات',ScrollText],['/admin/settings','إعدادات المركز',Settings]];
const memberLinks=[['/dashboard','نظرة عامة',LayoutDashboard],['/dashboard/courses','كورساتي',BookOpen],['/dashboard/research','الطلبات البحثية',Microscope],['/dashboard/payments','مدفوعاتي',Wallet],['/dashboard/profile','الملف الشخصي',UserRound]];
export const WorkspaceLayout=({admin=false})=>{
 const {user,logout}=useApp();
 const links=admin?adminLinks:user?.role==='employee'?memberLinks.filter(x=>x[0]==='/dashboard'||x[0].includes('profile')||x[0].includes('research')):memberLinks;
 return <div className="workspace"><aside className="workspace-side"><Logo/>
  <span className="workspace-label">{admin?'إدارة مركز كورا':user?.role==='employee'?'مساحة الموظف':'مساحتك التعليمية'}</span>
  <nav>{links.map(([to,label,Icon])=><NavLink end={to==='/admin'||to==='/dashboard'} key={to} data-testid={`workspace-${to.split('/').pop()}`} to={to}><Icon size={19}/>{label}</NavLink>)}</nav>
  <div className="sidebar-bottom"><Link data-testid="workspace-guide" title="دليل الاستخدام" aria-label="دليل الاستخدام" to={`/guide?role=${user?.role==='visitor'?'visitor':user?.role==='student'?'student':user?.role==='employee'?'employee':'admin'}`}><BookMarked size={17}/>دليل الاستخدام</Link><Link data-testid="back-to-site" to="/"><ArrowLeft size={17}/>العودة للموقع</Link><button data-testid="logout" onClick={logout}><LogOut size={17}/>تسجيل الخروج</button></div>
 </aside><div className="workspace-body"><header className="workspace-header"><span><ShieldCheck size={17}/>{admin?'لوحة الإدارة':'حساب كورا'}</span><Link data-testid="workspace-header-profile" to="/dashboard/profile"><span className="avatar-letter">{user?.name?.[0]}</span>{user?.name}</Link></header><div className="workspace-content"><Outlet/></div></div></div>;
};
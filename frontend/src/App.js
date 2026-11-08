import {useEffect} from 'react';
import {BrowserRouter,Routes,Route,useLocation,Link} from 'react-router-dom';
import {Toaster} from 'sonner';
import {AppProvider} from './context/AppContext';
import {PublicLayout,WorkspaceLayout,Protected} from './components/Layout';
import {Empty,Btn} from './components/Shared';
import Home from './pages/Home';
import Info from './pages/Info';
import Auth,{ActivateOwner} from './pages/Auth';
import Courses,{CourseDetail} from './pages/Courses';
import Dashboard,{Profile} from './pages/Dashboard';
import MyCourses from './pages/Library';
import Payments from './pages/Payments';
import AdminOverview,{AdminSettings,AdminAudit} from './pages/admin/AdminCore';
import AdminUsers from './pages/admin/AdminUsers';
import AdminCourses,{AdminLectures,AdminCategories} from './pages/admin/AdminCourses';
import AdminPurchases from './pages/admin/AdminPurchases';
import ResearchList from './pages/research/ResearchList';
import ResearchForm,{ResearchEntry} from './pages/research/ResearchForm';
import ResearchDetail from './pages/research/ResearchDetail';
import Posts from './pages/posts/Posts';
import PostDetail from './pages/posts/PostDetail';
import AdminPosts from './pages/posts/AdminPosts';
import {OperationsSummary} from './pages/admin/OperationsSummary';
import './App.css';
import './research.css';
import './features.css';
import './responsive-fixes.css';
const ScrollReset=()=>{const {pathname}=useLocation();useEffect(()=>{window.scrollTo(0,0);document.documentElement.lang='ar';document.documentElement.dir='rtl';document.title='كورا | منصة الأبحاث والتعليم الطبي';},[pathname]);return null;};
export default function App(){return <BrowserRouter><AppProvider><ScrollReset/><Routes>
 <Route element={<PublicLayout/>}>
  <Route index element={<Home/>}/>
  {['about','services','pricing','contact','privacy'].map(p=><Route key={p} path={p} element={<Info/>}/>)}
  {['login','register','forgot-password','reset-password'].map(p=><Route key={p} path={p} element={<Auth/>}/>)}
  <Route path="activate-owner" element={<ActivateOwner/>}/>
  <Route path="courses" element={<Courses/>}/><Route path="courses/:id" element={<CourseDetail/>}/>
  <Route path="research" element={<ResearchEntry/>}/><Route path="posts" element={<Posts/>}/><Route path="posts/:id" element={<PostDetail/>}/>
  <Route path="*" element={<Empty title="الصفحة غير موجودة" action={<Btn asChild data-testid="not-found-home"><Link to="/">العودة للرئيسية</Link></Btn>}/>}/>
 </Route>
 <Route element={<Protected/>}><Route path="dashboard" element={<WorkspaceLayout/>}>
  <Route index element={<Dashboard/>}/><Route path="courses" element={<MyCourses/>}/><Route path="payments" element={<Payments/>}/><Route path="profile" element={<Profile/>}/>
  <Route path="research" element={<ResearchList/>}/><Route path="research/new" element={<ResearchForm/>}/><Route path="research/:id" element={<ResearchDetail/>}/>
 </Route></Route>
 <Route element={<Protected admin/>}><Route path="admin" element={<WorkspaceLayout admin/>}>
  <Route index element={<><AdminOverview/><OperationsSummary/></>}/><Route path="users" element={<AdminUsers/>}/><Route path="courses" element={<AdminCourses/>}/><Route path="courses/:id" element={<AdminLectures/>}/><Route path="categories" element={<AdminCategories/>}/><Route path="purchases" element={<AdminPurchases/>}/><Route path="audit" element={<AdminAudit/>}/><Route path="settings" element={<AdminSettings/>}/>
  <Route path="research" element={<ResearchList/>}/><Route path="research/:id" element={<ResearchDetail/>}/><Route path="posts" element={<AdminPosts/>}/>
 </Route></Route>
 </Routes><Toaster position="top-center" dir="rtl" richColors closeButton/></AppProvider></BrowserRouter>;}
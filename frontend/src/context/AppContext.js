import {createContext,useContext,useState,useEffect} from 'react';
import {api} from '../lib/api';
const Context=createContext(null);
export const AppProvider=({children})=>{
 const [user,setUser]=useState(null),[loading,setLoading]=useState(true),[site,setSite]=useState(null),[categories,setCategories]=useState([]);
 const refresh=async()=>{try{setUser((await api.get('/auth/me')).data);}catch{setUser(null);}finally{setLoading(false);}};
 const loadSite=async()=>{const [s,c]=await Promise.all([api.get('/site'),api.get('/categories')]);setSite(s.data);setCategories(c.data);};
 useEffect(()=>{refresh();loadSite().catch(()=>{});},[]);
 const logout=async()=>{await api.post('/auth/logout');setUser(null);};
 return <Context.Provider value={{user,setUser,loading,refresh,logout,site,categories,loadSite}}>{children}</Context.Provider>;
};
export const useApp=()=>useContext(Context);
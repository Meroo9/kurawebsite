import axios from 'axios';
export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({baseURL:API,withCredentials:true,headers:{'X-Kura-Request':'1'}});
export const message = e => typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'تعذر إتمام العملية. يرجى المحاولة مجددًا';
export const money = (minor,currency) => `${new Intl.NumberFormat('ar',{maximumFractionDigits:2}).format((minor||0)/100)} ${currency||''}`;
export const date = value => value ? new Date(value).toLocaleDateString('ar',{year:'numeric',month:'short',day:'numeric'}) : '—';
export const upload = async (file,purpose,context,onProgress) => {const body=new FormData();body.append('file',file);body.append('purpose',purpose);body.append('context_id',context||'');return (await api.post('/files',body,{onUploadProgress:e=>onProgress?.(Math.round(e.loaded*100/(e.total||e.loaded)))})).data;};
export const fileUrl = (id,download=false) => `${API}/files/${id}${download?'?download=true':''}`;
import {useState} from 'react';
import {toast} from 'sonner';
import {api,message} from '../../lib/api';
import {Btn,Field,ErrorNotice} from '../../components/Shared';
export const KrcCorrection=({user,onDone})=>{
 const [krc,setKrc]=useState(user.krc),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const save=async()=>{setBusy(true);try{await api.patch(`/admin/users/${user.id}`,{krc});toast.success('تم تصحيح رقم كورا');onDone();}catch(e){setError(message(e));}finally{setBusy(false);}};
 return <div className="krc-correction"><Field id="admin-krc-input" label="تصحيح رقم كورا" dir="ltr" value={krc} onChange={e=>setKrc(e.target.value)}/><ErrorNotice text={error}/><Btn type="button" variant="outline" data-testid="save-krc-correction" disabled={busy||krc===user.krc} onClick={save}>حفظ رقم كورا</Btn></div>;
};
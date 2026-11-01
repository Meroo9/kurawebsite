import {useState} from 'react';
import {CalendarDays} from 'lucide-react';
import {ar} from 'date-fns/locale';
import {format} from 'date-fns';
import {Calendar} from './ui/calendar';
import 'react-day-picker/dist/style.css';
import {Popover,PopoverContent,PopoverTrigger} from './ui/popover';

export const DateInput=({id,value,onChange,required,max,disabled})=>{
 const [open,setOpen]=useState(false);
 const parsed=value&&/^\d{4}-\d{2}-\d{2}$/.test(value)?new Date(`${value}T12:00:00`):undefined;
 const selected=parsed&&!Number.isNaN(parsed.getTime())?parsed:undefined;
 const select=date=>{
  if(!date)return;
  onChange({target:{value:format(date,'yyyy-MM-dd')}});
  setOpen(false);
 };
 return <div className="date-input-wrap">
  <input id={id} data-testid={id} value={value||''} onChange={onChange} required={required} disabled={disabled} type="text" pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" dir="ltr" autoComplete="off"/>
  <Popover open={open} onOpenChange={setOpen}>
   <PopoverTrigger asChild><button type="button" disabled={disabled} className="date-trigger" data-testid={`${id}-calendar-button`} aria-label="اختيار تاريخ التسجيل"><CalendarDays size={19}/></button></PopoverTrigger>
   <PopoverContent className="calendar-popup" data-testid={`${id}-calendar`} align="end">
    <Calendar className="k-calendar" dir="rtl" locale={ar} mode="single" labels={{labelMonthDropdown:()=> 'الشهر',labelYearDropdown:()=> 'السنة',labelPrevious:()=> 'الشهر السابق',labelNext:()=> 'الشهر التالي'}} captionLayout="dropdown-buttons" fromYear={1990} toYear={new Date().getFullYear()} defaultMonth={selected} selected={selected} disabled={max?{after:new Date(`${max}T23:59:59`)}:undefined} onSelect={select} initialFocus/>
   </PopoverContent>
  </Popover>
 </div>;
};
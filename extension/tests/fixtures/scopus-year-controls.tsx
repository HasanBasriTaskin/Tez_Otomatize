// Local reproduction of the controlled draft/committed range used by Scopus (React 18.3.1).
import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';

function YearRange(){
  const [range,setRange]=useState({from:'',to:''});
  const [from,setFrom]=useState(''),[to,setTo]=useState('');
  useEffect(()=>{setFrom(range.from);setTo(range.to);},[range]);
  // Setting the first bound also fills the other bound from the available years.
  // Both decisions use the previous committed range, as the live Scopus component does.
  const commit=()=>setRange(previous=>{
    const next={...previous};
    if(previous.to!==to){next.to=to;if(to&&!previous.from)next.from='2000';if(!to&&previous.from)next.from='';}
    if(previous.from!==from){next.from=from;if(from&&!previous.to)next.to='2027';if(!from&&previous.to)next.to='';}
    return next;
  });
  return <div data-testid="facet-group-year">
    <input type="number" data-testid="input-range-from" value={from} onChange={e=>{setFrom(e.target.value);setTo(to);}} onBlur={commit}/>
    <input type="number" data-testid="input-range-to" value={to} onChange={e=>{setFrom(from);setTo(e.target.value);}} onBlur={commit}/>
    {(range.from||range.to)&&<button data-testid="apply-facet-range" aria-label="Apply selected year range" onClick={()=>{
      (window as any).appliedRange=range;
    }}>Apply selected year range</button>}
  </div>;
}
createRoot(document.querySelector('[data-testid="facet-s"]')!).render(<YearRange/>);

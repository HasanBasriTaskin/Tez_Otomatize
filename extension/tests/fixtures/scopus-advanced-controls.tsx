// Synthetic controlled editor: checks real React event/blur commit behavior, not live selector parity.
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
function Advanced(){
  const [draft,setDraft]=useState(''),[query,setQuery]=useState('');
  return <form onSubmit={e=>{e.preventDefault();(window as any).submittedQuery=query;}}>
    <textarea id="advancedQueryTextArea" aria-label="Advanced search query" value={draft}
      onChange={e=>setDraft(e.target.value)} onBlur={()=>setQuery(draft)}/>
    <button type="submit">Search</button>
  </form>;
}
const root=document.createElement('div');document.body.append(root);
flushSync(()=>createRoot(root).render(<Advanced/>));

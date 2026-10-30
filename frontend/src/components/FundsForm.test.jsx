import React from 'react';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {it,expect,vi,afterEach} from 'vitest';
import {FundsForm} from './FundsForm';
afterEach(()=>{cleanup();sessionStorage.clear();vi.restoreAllMocks();});
const ok=data=>({ok:true,json:async()=>data});
it('blocks recording when the register is closed',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(ok(null));
 render(<FundsForm user={{id:1}} onDone={()=>{}} />);
 await screen.findByText(/Open a cash register session/);
 expect(screen.getByRole('button',{name:'Post money movement'})).toBeDisabled();
});
it('recovers an uncertain supplier payment after remount using the same key',async()=>{
 const requests=[];
 vi.spyOn(globalThis,'fetch').mockImplementation(async(url,options)=>{
  if(url==='/api/register')return ok({id:1});
  requests.push([url,options]);if(requests.length===1)throw new Error('Lost response');return ok({id:42});
 });
 const done=vi.fn(),props={user:{id:1},purchase:{id:9,outstanding:'50'},onDone:done};
 const view=render(<FundsForm {...props}/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Record supplier payment'})).toBeEnabled());
 fireEvent.change(screen.getByLabelText('Amount'),{target:{value:'25'}});
 fireEvent.change(screen.getByLabelText('Reason / payment note'),{target:{value:'Verified payment'}});
 fireEvent.click(screen.getByRole('button',{name:'Record supplier payment'}));
 await screen.findByRole('button',{name:'Recover funds entry'});
 view.unmount();render(<FundsForm {...props}/>);
 fireEvent.click(screen.getByRole('button',{name:'Recover funds entry'}));
 await waitFor(()=>expect(done).toHaveBeenCalledTimes(1));
 expect(requests).toHaveLength(2);
 expect(requests[0][1].headers['Idempotency-Key']).toBe(requests[1][1].headers['Idempotency-Key']);
 expect(requests[0][1].body).toBe(requests[1][1].body);
 expect(sessionStorage.getItem('datus-pending-funds-1')).toBeNull();
});
it('requires a reference for external payments and clears it when switching to cash',async()=>{
 const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValue(ok({id:1}));
 render(<FundsForm user={{id:1}} purchase={{id:3,outstanding:'50'}} onDone={()=>{}}/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Record supplier payment'})).toBeEnabled());
 fireEvent.change(screen.getByLabelText('Payment source'),{target:{value:'external_mobile'}});
 expect(screen.getByLabelText('Verified transaction reference')).toBeRequired();
 fireEvent.change(screen.getByLabelText('Verified transaction reference'),{target:{value:'SHOULD-NOT-SEND'}});
 fireEvent.change(screen.getByLabelText('Payment source'),{target:{value:'cash'}});
 fireEvent.change(screen.getByLabelText('Amount'),{target:{value:'10'}});
 fireEvent.change(screen.getByLabelText('Reason / payment note'),{target:{value:'Paid in cash'}});
 fireEvent.click(screen.getByRole('button',{name:'Record supplier payment'}));
 await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url.includes('/payments'))).toBe(true));
 const request=fetcher.mock.calls.find(([url])=>url.includes('/payments'));
 expect(JSON.parse(request[1].body).reference).toBeNull();
});

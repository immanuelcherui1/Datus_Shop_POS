import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { it, expect, vi, afterEach } from 'vitest';
import { Purchases } from './Purchases';
afterEach(()=>{ cleanup(); vi.restoreAllMocks(); });
it('derives purchase costs and preserves an edited quote when converting units',async()=>{
 const p={id:1,name:'Sugar',active:true,quantity:'24',reorder_level:'0',unit:'kg',pack_size:'12',cost_per_unit:'100',cost_per_pack:'1200'};
 vi.spyOn(globalThis,'fetch').mockImplementation(async url=>({ok:true,json:async()=>({items:url.includes('/products')?[p]:[],pages:1})}));
 render(<Purchases user={{currency:'KES'}} notify={()=>{}} />);
 await screen.findByRole('option',{name:/Sugar/});
 fireEvent.change(screen.getByLabelText('Product 1'),{target:{value:'1'}});
 expect(screen.getByLabelText('Cost per selected unit 1')).toHaveValue(100);
 fireEvent.change(screen.getByLabelText('Unit 1'),{target:{value:'pack'}});
 expect(screen.getByLabelText('Cost per selected unit 1')).toHaveValue(1200);
 fireEvent.change(screen.getByLabelText('Quantity 1'),{target:{value:'5'}});
 expect(screen.getByText('Line: 6,000.00')).toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Cost per selected unit 1'),{target:{value:'600'}});
 fireEvent.change(screen.getByLabelText('Unit 1'),{target:{value:'unit'}});
 expect(screen.getByLabelText('Cost per selected unit 1')).toHaveValue(50);
 expect(screen.getByText('Line: 250.00')).toBeInTheDocument();
});

it('does not accumulate cost rounding when switching pack and unit repeatedly',async()=>{
 const p={id:1,name:'Pack of three',active:true,quantity:'3',unit:'piece',reorder_level:'0',pack_size:'3',cost_per_unit:'0.333333',cost_per_pack:'1'};
 vi.spyOn(globalThis,'fetch').mockImplementation(async url=>({ok:true,json:async()=>({items:url.includes('/products')?[p]:[],pages:1})}));
 render(<Purchases user={{currency:'KES'}} notify={()=>{}}/>);
 await screen.findByRole('option',{name:/Pack of three/});
 fireEvent.change(screen.getByLabelText('Product 1'),{target:{value:'1'}});
 for(let i=0;i<5;i++){
  fireEvent.change(screen.getByLabelText('Unit 1'),{target:{value:'pack'}});
  expect(screen.getByLabelText('Cost per selected unit 1')).toHaveValue(1);
  fireEvent.change(screen.getByLabelText('Unit 1'),{target:{value:'unit'}});
  expect(screen.getByLabelText('Cost per selected unit 1')).toHaveValue(0.333333);
 }
});
it('refuses an empty receipt before sending a mutation',async()=>{
 const order={id:1,supplier:{name:'Supplier'},status:'ordered',total:'10',lines:[{id:1,product_id:1,quantity:'3',received:'0',conversion:'3',pack_size_snapshot:'3',unit_cost:'3.333333',ordered_quantity:'1',ordered_unit_cost:'10'}]};
 const fetcher=vi.spyOn(globalThis,'fetch').mockImplementation(async url=>({ok:true,json:async()=>({items:url.startsWith('/api/purchases')?[order]:[],pages:1})}));
 render(<Purchases user={{currency:'KES'}} notify={()=>{}}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Confirm goods received'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Enter at least one delivered quantity');
 expect(fetcher.mock.calls.some(([url])=>url.includes('/receipts'))).toBe(false);
});

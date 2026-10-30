import {it,expect} from 'vitest';
import {convertedCost} from './cost';
it('converts six-decimal prices exactly with half-up rounding',()=>{
 expect(convertedCost('1','pack','unit',3)).toBe('0.333333');
 expect(convertedCost('1','pack','unit',6)).toBe('0.166667');
 expect(convertedCost('0.333333','unit','pack',3)).toBe('0.999999');
 expect(convertedCost('1','pack','pack',3)).toBe('1');
 expect(convertedCost('1.000001','pack','unit',2)).toBe('0.500001');
});

// Builds stand-in WOODWOP templates shaped like _2 TALL / _3 TALL (HANDOFF 10.4 and 10.5).
// Windows line ends and one Latin-1 byte (the a-umlaut in "Fraesen") so tests catch encoding damage.
'use strict';

function makeTemplate(slots, th) {
  const L = [];
  L.push('[H', 'VERSION="4.0 Alpha"', 'WW="6.0.68"', 'MAT="WEEKE"', 'INCH="0"',
    '_BSX=2438.000000', '_BSY=1219.200000', '_BSZ=10.000000', '');
  L.push('[001');
  const vars = [
    ['l', '2438', 'length'], ['w', '1219.2', 'width'], ['t', '10', 'thickness'],
    ['s', '337.55', 'side'], ['f', '555.625', 'front and back'], ['b', '6.35', 'bottom space and groove'],
    ['h', '47.625', 'box hight'], ['c', '12.7', '1/2 inch bit'], ['th', String(th), 'tray hight'],
    ['v', '4.76', 'velvet allowance']
  ];
  vars.forEach(([k, v, km]) => L.push(`${k}="${v}"`, `KM="${km}"`));
  for (let n = 1; n <= slots; n++) {
    L.push(`tr${n}w="102"`, `KM="tray ${n} width"`, `tr${n}d="102"`, `KM="tray ${n} depth"`);
  }
  L.push('');
  for (let n = 1; n <= slots; n++) {
    L.push(`]${n}`, '$E0', 'KP ', 'X=0', `Y=${8 + (n - 1) * 76}`, 'Z=0.0', '$E1', 'KL ',
      `X=tr${n}w+tr${n}d+tr${n}w+tr${n}d+40-(v*4)`, 'Y=@0', '');
  }
  L.push('<100 \\WerkStck\\', 'LA="l"', 'BR="w"', 'DI="t"', '');
  L.push('<105 \\Konturfraesen\\', 'EA="1:0"', 'TNO="130"', 'KAT="Fräsen"', 'MNM="Vertical trimming"', '');
  L.push('!');
  return L.join('\r\n') + '\r\n';
}

const SAMPLE_CSV = [
  'Order ID,Order Number,Lineitem Name,Lineitem Quantity,Lineitem Title,Width,Height,Depth',
  '9001,4354,Standard Jewelry Tray - Champagne / Custom Small,3,Standard Jewelry Tray,21 5/16,2,14 1/8',
  '9002,4357,"Standard Jewelry Tray - Blush / Small 22""W x 13 3/8""D",2,Standard Jewelry Tray,,,',
  '9003,4355,Watch Pillow Add-On,1,Watch Pillow Add-On,,,',
  '9004,4356,Standard Jewelry Tray - Black / Custom Large,1,Standard Jewelry Tray,31 5/16,3,19 3/4',
  '9004,4356,"Tray Measurement Charge - Extra Tray Height (3"")",1,Tray Measurement Charge,,,',
  '9005,4358,Valet Tray - Navy,1,Valet Tray,32,5,19',
  '9006,4360,Flat Liner - Black,1,Flat Liner,20,,12',
  '9007,4359,Custom Designed Trays - Medium / Navy,1,Custom Designed Trays,"24 7/8""",,13 3/8'
].join('\r\n') + '\r\n';

module.exports = { makeTemplate, SAMPLE_CSV };

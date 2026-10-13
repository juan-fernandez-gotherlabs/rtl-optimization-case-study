"""Generate portfolio LaTeX tables from the frozen64-pair evidence."""
from pathlib import Path
import hashlib,json,math,statistics,csv
CASE=Path(__file__).resolve().parents[1]
REPORT=CASE/'report/latex'
GEN=REPORT/'generated'
GEN.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((CASE/'results/confirmation64.json').read_text())
s=json.loads((CASE/'results/confirmation64-report-data.json').read_text())
assert sha(CASE/'results/confirmation64.json')=='2a39a8c018d80203413dc669316c185fc12a2e085e22f89f001a285d565999b4'
assert s['audited_result_sha256']==sha(CASE/'results/confirmation64.json')
assert len(r['all_rows'])==64
with (GEN/'executive-ci.csv').open('w',newline='') as h:
 w=csv.writer(h,lineterminator='\n');w.writerow(['x','metric','estimate','plus','minus'])
 for i,key in enumerate(['area_total_mwta','critical_path_delay_ns','active_total_power_w','composite'],1):
  z=s['metrics'][key];w.writerow([i,key,z['improvement_percent'],z['upper_improvement_percent']-z['improvement_percent'],z['improvement_percent']-z['lower_improvement_percent']])
with (GEN/'pair-clouds.csv').open('w',newline='') as h:
 names=['area','timing','power','composite'];primary=['area_total_mwta','critical_path_delay_ns','active_total_power_w']
 fields=['pair','seed','jitter']+[f'{side}_{n}' for side in ['baseline','optimized'] for n in names]
 w=csv.DictWriter(h,fieldnames=fields,lineterminator='\n');w.writeheader()
 reference={m:math.exp(statistics.mean(math.log(row['baseline'][m]) for row in r['all_rows'])) for m in primary}
 for i,row in enumerate(r['all_rows'],1):
  cloud={'pair':f'pair-{i:02d}','seed':row['seed'],'jitter':((i*37)%83)/83}
  for side in ['baseline','optimized']:
   vals={n:row[side][m]/reference[m] for n,m in zip(names,primary)}
   vals['composite']=math.exp(statistics.mean(math.log(v) for v in vals.values()))
   cloud.update({f'{side}_{n}':100*(1-v) for n,v in vals.items()})
  w.writerow(cloud)
macros={'EvidenceDate':'13 October 2026','PairCount':'64','CompositeScore':f"{r['statistics']['score']:.6f}",
 'CompositeMedian':f"{r['per_pair_composite_median']:.6f}",
 'FinalResultHash':sha(CASE/'results/confirmation64.json'),
 'BaselineRtlHash':'29b5ea77526b3b972ba99c8702524e87035e5a921db6f1a59bb822599203ba91',
 'OptimizedRtlHash':r['frozen_candidate_RTL_sha256'],
 'UpperOneSidedScore':f"{r['one_sided_95_upper_composite_score']:.6f}",
 'DelayLowerOneSidedRatio':f"{math.exp(r['statistics']['confidence']['metrics']['critical_path_delay_ns']['lower']):.6f}"}
for name,key in [('Area','area_total_mwta'),('Delay','critical_path_delay_ns'),('Power','active_total_power_w'),('Composite','composite')]:
 m=s['metrics'][key]
 for suffix,field in [('Improvement','improvement_percent'),('Low','lower_improvement_percent'),('High','upper_improvement_percent')]:
  macros[name+suffix]=f'{m[field]:.4f}'
 for suffix,field in [('Wins','wins'),('Ties','ties'),('Losses','losses')]:macros[name+suffix]=str(m[field])
d=s['metrics']['critical_path_delay_ns']
macros.update(DelayIncrease=f"{-d['improvement_percent']:.4f}",DelayIncreaseLow=f"{-d['upper_improvement_percent']:.4f}",DelayIncreaseHigh=f"{-d['lower_improvement_percent']:.4f}")
for label,prefix in [('baseline','Baseline'),('optimized','Optimized')]:
 g=s['geometric_aggregates'][label]
 macros[prefix+'Area']=f"{g['area_total_mwta']:,.0f}"
 macros[prefix+'Delay']=f"{g['critical_path_delay_ns']:.6f}"
 macros[prefix+'Power']=f"{1000*g['active_total_power_w']:.6f}"
 macros[prefix+'Fmax']=f"{g['delay_derived_frequency_mhz']:.4f}"
macros['FmaxReduction']=f"{100*(1-1/d['ratio']):.4f}"
values=[]
import csv
for row in csv.DictReader((GEN/'pair-clouds.csv').open()):
 values += [float(row[k]) for k in row if k.startswith(('baseline_','optimized_'))]
macros['CloudMin']=str(5*math.floor(min(values)/5)-5)
macros['CloudMax']=str(5*math.ceil(max(values)/5)+5)
(GEN/'metrics.tex').write_text(''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macros.items()))
for filename,rows in [('pairs-left.tex',r['all_rows'][:32]),('pairs-right.tex',r['all_rows'][32:])]:
 lines=[]
 for row in rows:
  vals=[100*(1-row['ratios'][key]) for key in ['area_total_mwta','critical_path_delay_ns','active_total_power_w']]
  vals.append(100*(1-row['composite_ratio']))
  printed=[]
  for i,v in enumerate(vals):
   cell=f'{v:.3f}'
   if i==1 and v<0:cell='\\textcolor{Regress}{'+cell+'}'
   printed.append(cell)
  lines.append(str(row['seed'])+' & '+' & '.join(printed)+' \\\\\n')
 (GEN/filename).write_text(''.join(lines))
# Preserve actual active-path excerpts and their source line numbers.
snippets={
 'wrapper.v':('serv_synth_wrapper.v',95,100),
 'rf-code.v':('serv_rf_ram_if.v',116,121),
 'decoder.v':('serv_decode.v',423,431),
 'address-code.v':('serv_bufreg.v',70,80),
 'pc-priority.v':('serv_ctrl.v',124,125),
}
for filename,(rtl,start,end) in snippets.items():
 lines=(CASE/'rtl/optimized'/rtl).read_text().splitlines()
 (GEN/filename).write_text('\n'.join(lines[start-1:end])+'\n')

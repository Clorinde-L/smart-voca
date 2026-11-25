# 강조색 팔레트 값 계산 (명도 대비 확인용 1회성)
def h2r(h): h=h.lstrip('#'); return [int(h[i:i+2],16)/255 for i in (0,2,4)]
def r2h(r): return '#'+''.join(f'{max(0,min(255,round(c*255))):02x}' for c in r)
def lum(h):
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    r,g,b=map(f,h2r(h)); return 0.2126*r+0.7152*g+0.0722*b
def cr(a,b): la,lb=sorted([lum(a),lum(b)],reverse=True); return (la+0.05)/(lb+0.05)
def mix(a,b,t): return r2h([x*(1-t)+y*t for x,y in zip(h2r(a),h2r(b))])
W,DS,DB='#ffffff','#181d2c','#0f1320'   # 밝은 표면, 어두운 표면, 어두운 배경
P={ # 이름: (밝게 primary, 어둡게 primary, 어둡게 on-primary)
 'indigo':('#4f5bd5','#7680ec','#ffffff'),
 'sea':   ('#0b74a0','#3fb0d9','#0f1320'),
 'forest':('#26804a','#4cbb78','#0f1320'),
 'rose':  ('#bf3a78','#ec75ad','#0f1320'),
 'sunset':('#c0521a','#f08f55','#0f1320'),
 'mono':  ('#3d4555','#c3c9d5','#0f1320'),
}
for n,(l,d,on) in P.items():
    print(f"/* {n}: 흰 글자 대비 {cr(l,W):.2f} / 어둡게 글자 대비 {cr(d,on):.2f}, 어두운 표면 위 글자 {cr(d,DS):.2f} */")
    v={
     'primary':(l,d),'primary-hover':(mix(l,'#000000',.12),mix(d,'#ffffff',.12)),'primary-pressed':(mix(l,'#000000',.24),mix(d,'#000000',.1)),
     'primary-soft':(mix(l,W,.9),mix(d,DS,.8)),'primary-soft-strong':(mix(l,W,.82),mix(d,DS,.7)),
     'primary-disabled':(mix(l,W,.6),mix(d,DS,.55)),'on-primary':('#ffffff',on),
     'hero-from':(mix(l,W,.08),mix(d,DB,.45)),'hero-to':(mix(l,'#000000',.2),mix(d,DB,.7)),'hero-muted':(mix(l,W,.82),mix(d,W,.6)),
    }
    print(f'[data-accent="{n}"] {{')
    for k,(a,b) in v.items(): print(f'  --{k}: light-dark({a}, {b});')
    print('}')

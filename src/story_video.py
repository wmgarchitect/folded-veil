"""40-second project film. Actual source geometry, measured values and viewer capture.

python src/story_video.py --preview
python src/story_video.py --render
Frames are streamed to bundled FFmpeg; no synthetic architectural imagery.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.deps'))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import veil as v
import field as fld
import nest

W, H, FPS, DURATION = 1080, 1920, 30, 40
S = 1.5
SW, SH = int(W*S), int(H*S)
OUT = ROOT / 'media' / 'FV-05-story'
OUT.mkdir(parents=True, exist_ok=True)
BG, INK, MUTED, GOLD = '#101513', '#F2EFE5', '#A0ADA3', '#D9B77A'
FONTS = Path('C:/Windows/Fonts')
RAD = fld.radial_field()
RAT = fld.rationalise(fld.depths_from(RAD), 5)
FIVE = [(d-v.D_MIN)/(v.DMAX_DEFAULT-v.D_MIN) for d in RAT]
ROWS = json.loads((ROOT / 'exports/FV-05-readback.json').read_text())
REPORT = json.loads((ROOT / 'exports/FV-05-validation.json').read_text())
NEST = json.loads((ROOT / 'nest_results.json').read_text())
FREE_RUN, FIVE_RUN = NEST['runs'][2:4]
EXTRA = 100*(FIVE_RUN['metal_m2']/FREE_RUN['metal_m2']-1)
TRACK_D = np.linspace(.2,.9,101)
TRACK_B = np.array([[v.piece_fold_angle(v.unit(f,float(d))) for f in RAD] for d in TRACK_D])
SPREAD = np.ptp(TRACK_B,axis=1)

def ease(t):
    t = max(0.,min(1.,t))
    return t*t*(3-2*t)

@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ('segoeuib.ttf' if bold else 'segoeui.ttf')), int(size*S))

def text(im, x,y, value, size=32, fill=INK, bold=False, anchor=None):
    ImageDraw.Draw(im).text((x*S,y*S),str(value),font=font(size,bold),fill=fill,anchor=anchor)

def line(im, coords, fill='#354139',width=1):
    ImageDraw.Draw(im).line([(x*S,y*S) for x,y in coords],fill=fill,width=max(1,int(width*S)))

def rounded(im,box,fill='#18201B',radius=18,outline=None):
    ImageDraw.Draw(im).rounded_rectangle(tuple(int(x*S) for x in box),radius=int(radius*S),fill=fill,outline=outline,width=2)

def background():
    yy,xx=np.mgrid[0:SH,0:SW]
    glow=np.maximum(0,1-np.sqrt(((xx-SW*.45)/(SW*.8))**2+((yy-SH*.48)/(SH*.55))**2))
    base=np.array([12,17,15])[None,None,:]+glow[:,:,None]*np.array([11,15,12])[None,None,:]
    return Image.fromarray(np.uint8(base))

BASE=background()

def chrome(im,chapter,t):
    text(im,72,68,'ARCHICODER',26,GOLD,True)
    text(im,1008,71,'FOLDED VEIL / 01—05',22,MUTED,anchor='ra')
    line(im,[(72,120),(1008,120)])
    text(im,72,1770,chapter.upper(),23,MUTED)
    text(im,1008,1770,'DESIGN STUDY · 2026',23,MUTED,anchor='ra')
    line(im,[(72,1824),(1008,1824)],'#354139',3)
    line(im,[(72,1824),(72+936*t/DURATION,1824)],GOLD,3)

def heading(im,number,lines,sub=None):
    text(im,72,165,number,25,GOLD)
    for i,s in enumerate(lines):text(im,72,220+i*85,s,68,INK,True)
    if sub:text(im,72,230+len(lines)*85,sub,29,MUTED)

def meshes(fs=RAD,dmax=.9,unit_index=None):
    tris=[]
    for i,(f,(col,row)) in enumerate(zip(fs,v.unit_positions())):
        if unit_index is not None and i!=unit_index:continue
        u=v.unit(f,dmax)
        p=np.array(u.points)+np.array([(col+.5)*1.5,0,(row+.5)*1.5])
        tris.extend(p[np.array(u.faces)])
    return np.array(tris)

def render_mesh(im,tris,box,angle=15,elev=7,color=(208,213,203),light_phase=0,highlight=None):
    """Orthographic depth-sorted triangle projection with directional diffuse shading."""
    th,el=math.radians(angle),math.radians(elev)
    view=np.array([math.sin(th)*math.cos(el),-math.cos(th)*math.cos(el),math.sin(el)])
    right=np.cross(np.array([0,0,1.]),view);right/=np.linalg.norm(right)
    up=np.cross(view,right)
    pts=tris.reshape(-1,3)
    centre=(pts.min(0)+pts.max(0))/2
    p=tris-centre
    proj=np.stack((p@right,-p@up),axis=-1)
    mins=proj.reshape(-1,2).min(0);maxs=proj.reshape(-1,2).max(0)
    x,y,bw,bh=box
    scale=min(bw/(maxs[0]-mins[0]),bh/(maxs[1]-mins[1]))*.96
    pp=(proj-(mins+maxs)/2)*scale+np.array([x+bw/2,y+bh/2])
    normals=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0])
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    normals[normals[:,1]>0]*=-1
    light=np.array([-.55+light_phase*.35,-.75,.72]);light/=np.linalg.norm(light)
    lam=np.maximum(0,normals@light)
    half=light+view;half/=np.linalg.norm(half)
    spec=np.maximum(0,normals@half)**18
    colors=np.clip(np.array(color)[None,:]*(.20+.77*lam[:,None])+spec[:,None]*34,0,255).astype(int)
    order=np.argsort(p.mean(1)@view)
    d=ImageDraw.Draw(im)
    for i in order:
        c=tuple(int(k) for k in colors[i])
        if highlight is not None and i//8==highlight:c=tuple(int(k) for k in np.clip(np.array([224,181,105])*(.5+.5*lam[i]),0,255))
        points=[tuple(k*S) for k in pp[i]]
        d.polygon(points,fill=c)
        d.line(points+[points[0]],fill=tuple(max(0,int(k*.66)) for k in c),width=1)

def metric(im,x,y,value,label):
    text(im,x,y,value,72,GOLD,True)
    text(im,x,y+96,label,28,MUTED)

def shot_intro(t):
    im=BASE.copy()
    heading(im,'01 / THE QUESTION',['The shape was','the easy part.'])
    render_mesh(im,meshes(),(40,535,1000,880),angle=24-22*ease(t/6),elev=9,light_phase=t/6)
    metric(im,72,1450,'88','folded units')
    metric(im,425,1450,'704','triangular faces')
    metric(im,770,1450,'1','radial field')
    text(im,72,1645,'Open at the entrance. Deeper towards the edges.',30,INK)
    chrome(im,'Form → measurement → exchange',t)
    return im

def shot_sweep(t):
    q=ease((t-6.8)/5.4);dmax=.2+.7*q
    lo,hi=min(v.piece_fold_angle(v.unit(f,dmax)) for f in RAD),max(v.piece_fold_angle(v.unit(f,dmax)) for f in RAD)
    im=BASE.copy();heading(im,'02 / TEST THE ASSUMPTION',['Shallower folds.','Wider angle range.'])
    render_mesh(im,meshes(dmax=dmax),(60,480,960,750),angle=19,elev=6)
    text(im,72,1250,f'{dmax*1000:.0f} mm',70,GOLD,True)
    text(im,72,1340,'maximum fold depth',27,MUTED)
    text(im,1008,1250,f'{hi-lo:.1f}°',70,INK,True,anchor='ra')
    text(im,1008,1340,'bend-angle spread',27,MUTED,anchor='ra')
    gx,gy,gw,gh=90,1440,900,165
    pts=[(gx+(d-.2)/.7*gw,gy+(28-b)/28*gh) for d,b in zip(TRACK_D,SPREAD)]
    line(im,[(gx,gy+gh),(gx+gw,gy+gh)],'#526058')
    line(im,pts,GOLD,3)
    px=gx+q*gw;py=gy+(28-(hi-lo))/28*gh
    ImageDraw.Draw(im).ellipse(((px-7)*S,(py-7)*S,(px+7)*S,(py+7)*S),fill=INK)
    text(im,gx,1623,'200 mm',24,MUTED);text(im,gx+gw,1623,'900 mm',24,MUTED,anchor='ra')
    text(im,72,1685,'Parameter study · not a moving facade mechanism',24,MUTED)
    chrome(im,'Measured geometry · same radial field',t)
    return im

def shot_families(t):
    im=BASE.copy();heading(im,'03 / SIMPLIFY, THEN MEASURE',['Fewer families.','More metal.'])
    render_mesh(im,meshes(),(90,475,900,485),angle=-4+8*ease((t-13)/7),elev=1)
    text(im,100,970,'26 families',38,INK,True);text(im,990,975,f"{FREE_RUN['metal_m2']:.1f} m²",34,MUTED,anchor='ra')
    render_mesh(im,meshes(FIVE),(90,1080,900,485),angle=-4+8*ease((t-13)/7),elev=1,color=(210,182,133))
    text(im,100,1570,'5 families',38,GOLD,True);text(im,990,1575,f'+{EXTRA:.1f}% metal',34,GOLD,anchor='ra')
    text(im,72,1675,'Groups use their deepest member. A measured trade-off.',26,MUTED)
    chrome(im,'Free gradient / five-family comparison',t)
    return im

PAIR_F=.4
PAIR_A=nest.piece_outline(PAIR_F)
PAIR_DX,PAIR_DY,_,_=nest.best_pair(PAIR_F)
PAIR_B=[(-x+PAIR_DX,-y+PAIR_DY) for x,y in PAIR_A]

def shot_nest(t):
    im=BASE.copy();heading(im,'04 / THE CUT SHEET',['Same pieces.','Better placement.'])
    q=ease((t-20)/3.5)
    bb=[(x,y+(1-q)*.35) for x,y in PAIR_B]
    a=np.array(PAIR_A);b=np.array(bb)
    allpts=np.array(PAIR_A+PAIR_B);mn=allpts.min(0);mx=allpts.max(0)
    scale=480
    center=np.array([540,890]);origin=(mn+mx)/2
    dr=ImageDraw.Draw(im)
    for points,col in [(a,'#B7C7B8'),(b,GOLD)]:
        transformed=(points-origin)*np.array([1,-1])*scale+center
        dr.polygon([tuple(p*S) for p in transformed],fill=col)
        dr.line([tuple(p*S) for p in np.concatenate([transformed,transformed[:1]])],fill=INK,width=2)
    text(im,540,1240,'One blank + its 180° rotation',30,MUTED,anchor='ma')
    text(im,540,1350,f"{FREE_RUN['sheets_one_up']} → {FREE_RUN['sheets_paired']}",130,GOLD,True,anchor='ma')
    text(im,540,1525,'sheets across the free-gradient facade',31,INK,anchor='ma')
    text(im,540,1610,'2000 × 4000 mm stock · shelf-packing estimate',27,MUTED,anchor='ma')
    text(im,540,1660,'Illustrated pair: f = 0.4 · counts are upper bounds',24,MUTED,anchor='ma')
    chrome(im,'352 sheet pieces · 3 mm kerf · 10 mm trim',t)
    return im

def shot_bim(t):
    im=BASE.copy();heading(im,'05 / KEEP THE DATA',['Every unit carries','its own evidence.'])
    record=ROWS[87];tris=np.array(record['vertices'])[np.array(record['faces'])]
    render_mesh(im,tris,(155,470,770,610),angle=18+14*ease((t-26)/8),elev=13,color=(222,187,125))
    rounded(im,(72,1140,1008,1645),'#1B241E',22,'#53644F')
    text(im,105,1175,'FV-088',42,GOLD,True);text(im,974,1188,'IFC4 / ARC_Fabrication',25,MUTED,anchor='ra')
    for j,(key,label,suffix) in enumerate([('depth_mm','Fold depth',' mm'),('bend_deg','Bend angle','°'),('blank_h_mm','Blank height',' mm'),('pieces','Pieces per unit','')]):
        y=1260+j*80
        text(im,105,y,label,32,MUTED);text(im,974,y,str(record['properties'][key])+suffix,35,INK,True,anchor='ra')
        if j<3:line(im,[(105,y+59),(974,y+59)])
    text(im,72,1680,'Geometry + values read back from the exported IFC.',26,MUTED)
    chrome(im,'Python → IFC4 → Speckle',t)
    return im

@lru_cache(maxsize=80)
def captured(path):
    return Image.open(path).convert('RGB')

def shot_speckle(t):
    im=BASE.copy();heading(im,'06 / OPEN IT ELSEWHERE',['The model is live.'], 'Geometry and fabrication properties in Speckle.')
    directory=ROOT/'media/FV-05-story/capture'
    manifest=directory/'frames.json'
    if manifest.exists():
        frames=json.loads(manifest.read_text());rel=min(t-34,frames[-1]['time'])
        frame=min(frames,key=lambda f:abs(f['time']-rel))
        screen=captured(str(directory/frame['file']))
    else:
        screen=captured(str(ROOT/'media/FV-05-speckle-overview.jpg'))
    # Preserve the actual screen's aspect ratio, including current browser size.
    scale=min(936/screen.width,570/screen.height)
    bw,bh=screen.width*scale,screen.height*scale
    screen=screen.resize((int(bw*S),int(bh*S)),Image.Resampling.LANCZOS)
    im.paste(screen,(int((W-bw)/2*S),int(460*S)))
    text(im,72,1065,'FV-088 / PROPERTIES IN SPECKLE',26,GOLD)
    # A clearly identified excerpt of the actual earlier viewer screenshot.
    props=captured(str(ROOT/'media/FV-05-speckle-FV088.jpg')).crop((0,538,445,825))
    props=props.resize((int(936*S),int(936*props.height/props.width*S)),Image.Resampling.LANCZOS)
    im.paste(props,(int(72*S),int(1120*S)))
    text(im,540,1738,'Screen recording + property capture · model link in first comment',23,MUTED,anchor='ma')
    chrome(im,'Concept model · no thickness or connections',t)
    return im

SCENES=[(0,shot_intro),(6,shot_sweep),(13,shot_families),(20,shot_nest),(26,shot_bim),(34,shot_speckle)]

def frame(t):
    ix=max(i for i,(start,_) in enumerate(SCENES) if t>=start)
    im=SCENES[ix][1](t)
    start=SCENES[ix][0]
    if ix and t-start<.38:
        prev=SCENES[ix-1][1](start-1/FPS)
        im=Image.blend(prev,im,ease((t-start)/.38))
    return im.resize((W,H),Image.Resampling.LANCZOS)

def preview():
    times=[2,6.7,12.5,16,23.5,29.5,36]
    contact=Image.new('RGB',(360*4,640*2),'#0C100E')
    for i,t in enumerate(times):
        im=frame(t);im.save(OUT/f'preview-{t:04.1f}.jpg',quality=94)
        contact.paste(im.resize((360,640)),((i%4)*360,(i//4)*640))
    contact.save(OUT/'contact-sheet.jpg',quality=94)
    frame(2).save(OUT/'FV-05-cover.jpg',quality=96)
    print(OUT/'contact-sheet.jpg',flush=True)

def render():
    target=OUT/'FV-05-project-story.mp4'
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo',
         '-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264',
         '-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    start=time.time()
    try:
        for i in range(FPS*DURATION):
            process.stdin.write(frame(i/FPS).tobytes())
            if i%90==0:print(f'{i}/{FPS*DURATION} frames; {time.time()-start:.0f}s',flush=True)
    finally:
        process.stdin.close()
    if process.wait()!=0:raise RuntimeError('Video encoding failed')
    print(target,flush=True)

if __name__=='__main__':
    args=argparse.ArgumentParser();args.add_argument('--preview',action='store_true');args.add_argument('--render',action='store_true')
    a=args.parse_args()
    if a.preview:preview()
    if a.render:render()

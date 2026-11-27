from PIL import Image, ImageDraw
import sys
def make(size, rounded=True, scale=1.0, bg=True):
    S=2048; k=S/512
    im=Image.new("RGBA",(S,S),(0,0,0,0)); d=ImageDraw.Draw(im)
    # gradient bg
    g=Image.new("RGBA",(S,S))
    gp=g.load()
    c1=(7,26,69); c2=(22,59,143)
    for y in range(S):
        for x in range(0,S,1):
            t=(x+y)/(2*S); gp[x,y]=tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))+(255,)
    mask=Image.new("L",(S,S),0); md=ImageDraw.Draw(mask)
    if rounded: md.rounded_rectangle([0,0,S-1,S-1],radius=int(112*k),fill=255)
    else: md.rectangle([0,0,S,S],fill=255)
    im.paste(g,(0,0),mask)
    # glyph, scaled about centre
    def P(x,y): return (S/2+(x-256)*k*scale, S/2+(y-256)*k*scale)
    w=int(68*k*scale); r=w/2
    d.line([P(296,196),P(296,300)],fill="white",width=w)
    for q in (P(296,196),): d.ellipse([q[0]-r,q[1]-r,q[0]+r,q[1]+r],fill="white")
    c=P(208,300); R=88*k*scale+w/2
    d.arc([c[0]-R,c[1]-R,c[0]+R,c[1]+R],0,180,fill="white",width=w)
    q=P(120,300); d.ellipse([q[0]-r,q[1]-r,q[0]+r,q[1]+r],fill="white")
    q=P(296,300); d.ellipse([q[0]-r,q[1]-r,q[0]+r,q[1]+r],fill="white")
    q=P(296,120); rr=40*k*scale; d.ellipse([q[0]-rr,q[1]-rr,q[0]+rr,q[1]+rr],fill=(255,153,51,255))
    return im
for name,size,rounded,scale in [("icon-512.png",512,True,1),("icon-192.png",192,True,1),("favicon-32.png",32,True,1),("favicon-16.png",16,True,1),("apple-touch-icon.png",180,False,.92),("maskable-512.png",512,False,.72)]:
    make(size,rounded,scale).resize((size,size),Image.LANCZOS).save(name)
# og image 1200x630
og=Image.new("RGB",(1200,630),(7,26,69)); gp=og.load()
for y in range(630):
    for x in range(1200):
        t=(x/1200*0.6+y/630*0.4); gp[x,y]=tuple(int(a+(b-a)*t) for a,b in zip((7,26,69),(22,59,143)))
from PIL import ImageFont
ic=make(512,True,1).resize((260,260),Image.LANCZOS); og.paste(ic,(90,185),ic)
d=ImageDraw.Draw(og)
def font(sz,b=True):
    for p in ["/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try: return ImageFont.truetype(p,sz)
        except Exception: pass
    return ImageFont.load_default()
d.text((400,200),"JANSEVA AI",font=font(84),fill="white")
d.text((400,310),"One Photo. One Voice.",font=font(42),fill="white")
d.text((400,365),"One Accountable India.",font=font(42),fill=(255,153,51))
d.text((400,450),"Report a civic problem. Track it until it is really fixed.",font=font(26),fill=(200,214,245))
d.rectangle([0,618,1200,630],fill=(255,153,51))
og.save("og.png")
# ico
make(256,True,1).resize((256,256),Image.LANCZOS).save("favicon.ico",sizes=[(16,16),(32,32),(48,48),(64,64)])

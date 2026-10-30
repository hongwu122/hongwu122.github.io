# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, re, threading, webbrowser, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus
from urllib.request import Request, urlopen
from books_assets import store_asset
ROOT=Path(__file__).resolve().parent
BOOKS=ROOT/'books.json'; SHELF=ROOT.parent/'asset'/'local-data'/'lab_shelves.json'; HOST='127.0.0.1'; PORT=8769
ALIASES={
'生而液态':'Born Liquid Transformations in the Third Millennium Zygmunt Bauman Thomas Leoncini','艰难时代':'Hard Times An Oral History of the Great Depression Studs Terkel','金融化与不平等':'Divested Inequality in the Age of Finance Ken-Hou Lin Megan Tobias Neely','我们时代的神经症人格':'The Neurotic Personality of Our Time Karen Horney','新教伦理与资本主义精神':'The Protestant Ethic and the Spirit of Capitalism Max Weber','乌合之众':'The Crowd A Study of the Popular Mind Gustave Le Bon','自卑与超越':'What Life Should Mean to You Alfred Adler','墙：血与砖的史':'Walls A History of Civilization in Blood and Brick David Frye'}
KNOWN={
'生而液态':{'title':'生而液态','author':'齐格蒙特·鲍曼 / 托马斯·莱昂奇尼','isbn':'9787523613771','url':'https://book.douban.com/subject/37336524/','platform':'豆瓣读书','cover':'https://books.google.com/books/content?id=BGh-DwAAQBAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'艰难时代':{'title':'艰难时代','author':'斯特兹·特克尔','isbn':'9787508667256','url':'https://books.google.com/books?id=4_6MtQEACAAJ','platform':'Google Books','cover':'https://books.google.com/books/content?id=4_6MtQEACAAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'金融化与不平等':{'title':'金融化与不平等','author':'林庚厚 / 梅根·尼利','isbn':'9787300333991','url':'https://opac.uibe.edu.cn/opac/book/cc4f9bb7a2eba823e6f49edea0b85369','platform':'图书馆书目','cover':'https://books.google.com/books/content?id=hMHADwAAQBAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'我们时代的神经症人格':{'title':'我们时代的神经症人格','author':'卡伦·霍妮','url':'https://books.google.com/books?id=Kt9l6ev2JG8C','platform':'Google Books','cover':'https://books.google.com/books/content?id=Kt9l6ev2JG8C&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'新教伦理与资本主义精神':{'title':'新教伦理与资本主义精神','author':'马克斯·韦伯','url':'https://books.google.com/books?id=Ki0MswEACAAJ','platform':'Google Books','cover':'https://books.google.com/books/content?id=Ki0MswEACAAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'乌合之众':{'title':'乌合之众','author':'古斯塔夫·勒庞','url':'https://books.google.com/books?id=XaDWAAAAMAAJ','platform':'Google Books','cover':'https://books.google.com/books/content?id=XaDWAAAAMAAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'自卑与超越':{'title':'自卑与超越','author':'阿尔弗雷德·阿德勒','url':'https://books.google.com/books?id=7gYLEgAAQBAJ','platform':'Google Books','cover':'https://books.google.com/books/content?id=7gYLEgAAQBAJ&printsec=frontcover&img=1&zoom=1&source=gbs_api'},
'墙：血与砖的史':{'title':'墙：血与砖的史','author':'David Frye','url':'https://www.google.com/search?tbm=bks&q=Walls+A+History+of+Civilization+in+Blood+and+Brick+David+Frye','platform':'Google 图书搜索','cover':''}}
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)
def load(path,default):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except:return default
def http_json(url):
 req=Request(url,headers={'User-Agent':'HongwuBooks/1.1'}); return json.loads(urlopen(req,timeout=8).read().decode('utf-8','replace'))
def norm(v):return re.sub(r'[^a-z0-9\u4e00-\u9fff]+','',str(v or '').lower())
def score(q,a,t,authors):
 nq,nt=norm(q),norm(t); s=120 if nq and nq==nt else 70 if nq and (nq in nt or nt in nq) else 0
 if a and norm(a) in norm(' '.join(authors or [])):s+=45
 return s
def lookup(title,author='',isbn='',platform=''):
 title=(title or '').strip(); author=(author or '').strip(); isbn=re.sub(r'[^0-9Xx]','',isbn or '')
 queries=[]
 if isbn:queries.append('isbn:'+isbn)
 if title and author:queries.append('intitle:'+title+' inauthor:'+author)
 if title:queries.append('intitle:'+title)
 if title in ALIASES:queries.append(ALIASES[title])
 c=[]
 for q in ([] if platform=='openlibrary' else queries[:6]):
  try:
   d=http_json('https://www.googleapis.com/books/v1/volumes?maxResults=10&printType=books&q='+quote_plus(q))
   for it in d.get('items') or []:
    v=it.get('volumeInfo') or {}; ids=v.get('industryIdentifiers') or []; sc=score(title,author,v.get('title',''),v.get('authors') or [])+(40 if isbn and any(re.sub(r'[^0-9Xx]','',x.get('identifier',''))==isbn for x in ids) else 0); c.append({'title':v.get('title') or title,'author':' / '.join(v.get('authors') or []),'publisher':v.get('publisher',''),'published':v.get('publishedDate',''),'cover':((v.get('imageLinks') or {}).get('thumbnail') or (v.get('imageLinks') or {}).get('smallThumbnail') or '').replace('http:','https:'),'url':v.get('infoLink') or ('https://books.google.com/books?id='+str(it.get('id') or '')),'platform':'Google Books','isbn':next((x.get('identifier','') for x in ids if x.get('type')=='ISBN_13'),''),'score':sc})
  except:pass
 if c:
  c.sort(key=lambda x:(x['score'],bool(x['cover'])),reverse=True)
  if c[0]['score']>=60:
   b=c[0]; b.pop('score',None); return {'ok':True,'best':b,'alternatives':[{k:v for k,v in x.items() if k!='score'} for x in c[1:5] if x.get('score',0)>=35]}
 for q in ([] if platform=='google' else [title,ALIASES.get(title,'')]):
  if not q:continue
  try:
   d=http_json('https://openlibrary.org/search.json?limit=10&q='+quote_plus(q)); docs=d.get('docs') or []
   if docs:
    b=max(docs,key=lambda x:score(title,author,x.get('title',''),x.get('author_name') or [])); sc=score(title,author,b.get('title',''),b.get('author_name') or [])
    if sc>=60:
     return {'ok':True,'best':{'title':b.get('title') or title,'author':' / '.join(b.get('author_name') or []),'publisher':(b.get('publisher') or [''])[0],'published':str(b.get('first_publish_year') or ''),'cover':'https://covers.openlibrary.org/b/id/%s-L.jpg'%b.get('cover_i') if b.get('cover_i') else '', 'url':'https://openlibrary.org'+b.get('key','') if b.get('key') else 'https://openlibrary.org/search?q='+quote_plus(q),'platform':'Open Library','isbn':(b.get('isbn') or [''])[0]},'alternatives':[]}
  except:pass
 q=(ALIASES.get(title) or (title+' '+author)).strip(); return {'ok':False,'best':{'title':title,'author':author,'cover':'','url':'https://www.google.com/search?tbm=bks&q='+quote_plus(q),'platform':'Google 图书搜索','isbn':isbn},'message':'没有达到可靠匹配阈值，未自动绑定错误书目；已生成更精确的图书搜索入口。'}
def sync_shelf(data):
 books=data.get('books',[]) if isinstance(data,dict) else []; shelf=load(SHELF,{}); ranked=[b for b in books if b.get('favorite')][:4]; shelf['reading']=[{'id':b.get('id',''),'title':b.get('title',''),'meta':b.get('author') or b.get('status') or '私藏书库','url':'./books/?open='+quote_plus(str(b.get('id') or b.get('title') or '')),'cover':('./books/'+b['cover'] if b.get('cover') and not b['cover'].startswith(('http:','https:','/')) else b.get('cover','')),'platform':b.get('platform','私藏书库')} for b in ranked if b.get('title')]; shelf['updated']=time.strftime('%Y-%m-%d'); atomic(SHELF,shelf)
class H(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
 def reply(self,d,status=200):
  raw=json.dumps(d,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
 def do_GET(self):
  u=urlparse(self.path)
  if u.path=='/api/books/status':return self.reply({'ok':True,'service':'books','port':PORT})
  if u.path=='/api/books/lookup':
   q=parse_qs(u.query)
   try:return self.reply(lookup((q.get('title') or q.get('q') or [''])[0],(q.get('author') or [''])[0],(q.get('isbn') or [''])[0],(q.get('platform') or [''])[0]))
   except Exception as e:return self.reply({'ok':False,'message':str(e)},400)
  return super().do_GET()
 def do_POST(self):
  if urlparse(self.path).path=='/api/books/asset':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<=0 or n>36*1024*1024:raise ValueError('文件大小不正确')
    return self.reply(store_asset(json.loads(self.rfile.read(n).decode())))
   except Exception as e:return self.reply({'ok':False,'message':str(e)},400)
  if urlparse(self.path).path!='/api/books/save':return self.reply({'ok':False,'message':'not found'},404)
  try:
   n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n).decode()); expected=data.pop('_base_books',None)
   if expected is not None and expected!=load(BOOKS,{}).get('books',[]):return self.reply({'ok':False,'message':'书库已在其他页面更新，请刷新后再编辑。'},409)
   atomic(BOOKS,data); sync_shelf(data); return self.reply({'ok':True,'message':'books.json 已保存并同步 Lab 私藏书架。'})
  except Exception as e:return self.reply({'ok':False,'message':str(e)},400)
if __name__=='__main__':
 print('私藏书库维护：http://127.0.0.1:%s/'%PORT)
 if not os.environ.get('HONGWU_LAUNCHED_BY_HUB'):threading.Timer(.6,lambda:webbrowser.open('http://127.0.0.1:%s/'%PORT)).start()
 try:ThreadingHTTPServer((HOST,PORT),H).serve_forever()
 except KeyboardInterrupt:pass

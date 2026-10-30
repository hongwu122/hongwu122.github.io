from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import hashlib, base64, json, re, html
ROOT=Path(__file__).resolve().parent

def store_asset(body):
    kind=body.get('kind','cover')
    if kind=='source':
        url=body.get('url','')
        if urlparse(url).scheme not in ('http','https'):raise ValueError('请输入 HTTP 或 HTTPS 平台链接')
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=12) as response:
            text=response.read(2*1024*1024).decode('utf-8','replace')
            match=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
            return {'ok':True,'status':response.status,'url':response.geturl(),'title':html.unescape(re.sub('<[^>]+>','',match.group(1))).strip() if match else '页面没有提供书名标题'}
    if body.get('data'):
        raw=base64.b64decode(body['data'],validate=True)
        mime=body.get('mime','')
    else:
        url=body.get('url','')
        if urlparse(url).scheme not in ('http','https'):raise ValueError('请提供 HTTP 或 HTTPS 链接')
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as r:
            mime=r.headers.get_content_type();raw=r.read(25*1024*1024+1)
    if hashlib.sha256(raw).hexdigest().startswith('e3f8c414b288cbdf4e6d1e00'):raise ValueError('平台返回 image not available 占位图，请更换来源')
    if len(raw)>25*1024*1024:raise ValueError('文件超过 25 MB，请直接放入 books 目录后填写相对路径')
    if kind=='pdf':
        if not raw.startswith(b'%PDF-'):raise ValueError('文件不是 PDF')
        folder='pdfs';ext='.pdf'
    else:
        folder='covers'
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):ext='.png'
        elif raw.startswith(b'\xff\xd8\xff'):ext='.jpg'
        elif raw.startswith((b'GIF87a',b'GIF89a')):ext='.gif'
        elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':ext='.webp'
        else:raise ValueError('链接未返回有效的 PNG、JPG、GIF 或 WebP 封面')
    target=ROOT/folder/(hashlib.sha256(raw).hexdigest()[:24]+ext)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return {'ok':True,'path':target.relative_to(ROOT).as_posix()}

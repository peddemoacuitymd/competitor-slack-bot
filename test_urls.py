import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})

url = "https://blog.featured.com/sitemap/"
print(f"Fetching {url}...")
response = session.get(url, timeout=15)
print(f"Status: {response.status_code}, Content length: {len(response.content)}")

soup = BeautifulSoup(response.content, 'html.parser')
links = soup.find_all('a', href=True)
print(f"Total links found: {len(links)}")

base_url = "https://blog.featured.com"
article_urls = []

for link in links:
    href = link.get('href', '')
    
    if href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
        continue
    
    if href.startswith('/'):
        full_url = urljoin(base_url, href)
    elif href.startswith('http'):
        full_url = href
    else:
        continue
    
    if 'blog.featured.com' not in full_url:
        continue
    
    exclude_patterns = [
        '/sitemap', '/about', '/login', '/signup', '/contact', 
        '/privacy', '/terms', '/publishers', '/home', '/category/', 
        '/tag/', '/author/', '/page/', '/search'
    ]
    
    should_exclude = any(pattern in full_url.lower() for pattern in exclude_patterns)
    path = urlparse(full_url).path
    is_root = not path or path == '/' or path.strip('/') == ''
    
    if not should_exclude and not is_root and full_url not in article_urls:
        article_urls.append(full_url)

print(f"\nArticle URLs found: {len(article_urls)}")
print(f"First 5: {article_urls[:5]}")





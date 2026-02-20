import requests
from bs4 import BeautifulSoup

# Test with session (like main script)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
})

url = "https://blog.featured.com/sitemap/"
response = session.get(url)
print(f"Status: {response.status_code}")
print(f"Content length: {len(response.content)}")

soup = BeautifulSoup(response.content, 'html.parser')
links = soup.find_all('a', href=True)
print(f"Links found: {len(links)}")





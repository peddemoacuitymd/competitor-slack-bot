import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
})

url = "https://blog.featured.com/sitemap/"
response = session.get(url)
print(f"Status code: {response.status_code}")
print(f"Content length: {len(response.content)}")

soup = BeautifulSoup(response.content, 'html.parser')

# Check for different structures
print("\n=== Checking for links ===")
links = soup.find_all('a', href=True)
print(f"Total links found: {len(links)}")

# Filter for blog.featured.com links that look like articles
article_links = []
for link in links:
    href = link.get('href', '')
    if 'blog.featured.com' in href and '/category/' not in href and '/sitemap' not in href and '/about' not in href:
        article_links.append((href, link.get_text(strip=True)[:50]))

print(f"\nPotential article links: {len(article_links)}")
for i, (href, text) in enumerate(article_links[:30]):  # Show first 30
    print(f"{i+1}. {href} - Text: {text}")

print("\n=== Checking for list items ===")
list_items = soup.find_all('li')
print(f"Total list items: {len(list_items)}")
for i, li in enumerate(list_items[:10]):
    print(f"{i+1}. {li.get_text(strip=True)[:100]}")

print("\n=== Checking for article/post containers ===")
# Look for common article container patterns
article_containers = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in str(x).lower() or 'article' in str(x).lower()))
print(f"Article containers: {len(article_containers)}")


import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# Find Matthew in Chuukese NT
print("=== Finding Matthew in Chuukese NT ===")
book = epub.read_epub('data/bible/nwt_TE.epub')

# Check TOC
for item in book.get_items():
    if item.get_name() == 'toc.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        links = soup.find_all('a', href=True)
        print("First 15 TOC entries:")
        for link in links[:15]:
            text = link.get_text().strip()
            href = link['href']
            if 'matthew' in text.lower() or 'mateo' in text.lower() or text.startswith('40'):
                print(f"  >>> {text}: {href}")
            else:
                print(f"  {text}: {href}")
        break

# Look for chapter navigation for book 40
print("\n=== Looking for Matthew chapter navigation ===")
for item in book.get_items():
    if 'chapternav40' in item.get_name():
        print(f"Found: {item.get_name()}")
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        links = soup.find_all('a', href=True)
        print(f"Chapter links:")
        for link in links[:30]:
            print(f"  Chapter {link.get_text().strip()}: {link['href']}")
        break

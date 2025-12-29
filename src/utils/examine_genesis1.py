import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

book = epub.read_epub('data/bible/nwt_E.epub')
for item in book.get_items():
    if item.get_name() == '1001061105.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        print("=== Genesis Chapter 1 Structure ===\n")
        
        # Find all elements with IDs
        elements_with_ids = soup.find_all(id=True)
        print(f"Total elements with IDs: {len(elements_with_ids)}")
        
        # Show first 30 IDs
        for elem in elements_with_ids[:30]:
            elem_id = elem.get('id')
            data_pid = elem.get('data-pid')
            text = elem.get_text().strip()[:80]
            print(f"id={elem_id}, data-pid={data_pid}")
            if text and len(text) > 10:
                print(f"  text: {text}")
        
        break

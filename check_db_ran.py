from src.database.connection import DatabaseConnection
from src.database.models import WordEntry

db = DatabaseConnection()
words = list(db.words.find({'chuukese': 'ran'}))
print(f'Found {len(words)} entries with chuukese="ran" in database')
for word in words[:3]:
    print(f'Chuukese: {word.get("chuukese")}')
    print(f'English: {word.get("english")}')
    print(f'Grammar: {word.get("grammar")}')
    print('---')
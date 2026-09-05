from enhanced_trainer import EnhancedHelsinkiTrainer
trainer = EnhancedHelsinkiTrainer()
chk_pairs, en_pairs = trainer.prepare_enhanced_training_data()

# Find entries where chuukese ends with 'ran' or starts with 'ran'
ran_exact = [p for p in chk_pairs if p.get('chuukese', '').strip().endswith(' ran') or p.get('chuukese', '').strip() == 'ran' or ' ran' in p.get('chuukese', '')]
print(f'Found {len(ran_exact)} entries with exact "ran" in chuukese')
for entry in ran_exact[:10]:
    print(f'Chuukese: "{entry.get("chuukese")}"')
    print(f'English: "{entry.get("english")}"')
    print(f'Grammar: "{entry.get("grammar")}"')
    print('---')
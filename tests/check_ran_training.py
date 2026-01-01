from enhanced_trainer import EnhancedHelsinkiTrainer
trainer = EnhancedHelsinkiTrainer()
chk_pairs, en_pairs = trainer.prepare_enhanced_training_data()

# Find entries with 'ran' in chuukese
ran_entries = [p for p in chk_pairs if 'ran' in p.get('chuukese', '')]
print(f'Found {len(ran_entries)} entries with "ran" in chuukese')
for entry in ran_entries[:5]:
    print(f'Chuukese: "{entry.get("chuukese")}"')
    print(f'English: "{entry.get("english")}"')
    print(f'Grammar: "{entry.get("grammar")}"')
    print('---')
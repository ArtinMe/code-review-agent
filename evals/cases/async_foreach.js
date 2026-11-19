export async function saveAll(db, records) {
  let saved = 0;
  records.forEach(async (record) => {
    await db.insert("records", record);
    saved += 1;
  });
  return saved;
}

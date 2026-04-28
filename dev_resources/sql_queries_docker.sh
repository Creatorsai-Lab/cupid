# Open an Interactive psql Shell
docker exec -it cupid_postgres psql -U cupid -d cupid_db
# You would see the prompt changes to cupid_db=#. Now run any SQL
# NOTE: Type `\q` to exit. Inside this shell, every line ending with `;` is sent to Postgres.

# Count of Trending articles
SELECT COUNT(*) FROM trending_articles;

# query some articles
SELECT category, title, source FROM trending_articles LIMIT 5;

# Most recent 5 articles
SELECT title, source, category FROM trending_articles ORDER BY published_at DESC LIMIT 5;

# Show table structure

# ALERT! Wipe the table and start fresh (use carefully!)
DELETE FROM trending_articles;

# Find user ID
SELECT id, email FROM users;
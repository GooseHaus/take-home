import os

# Must be set before app.db is imported: tests never touch data/app.db or real keys.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

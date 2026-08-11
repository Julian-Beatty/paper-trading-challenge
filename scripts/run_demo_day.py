"""Run the API with uvicorn, then use /docs to execute a deterministic demo day."""

# Responsibility: keep run demo day concerns isolated and readable.

print("Start with: uvicorn app.main:app --reload")
print("Then open: http://127.0.0.1:8000/docs")

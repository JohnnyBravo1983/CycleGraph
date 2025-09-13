# Eksempel på tokens.py – fyll inn dine egne API-nøkler her
def load_tokens():
    return {
        "access_token": "..."
    }

def build_headers():
    tokens = load_tokens()
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Content-Type": "application/json"
    }

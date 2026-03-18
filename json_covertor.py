import json
import firebase_admin
from firebase_admin import credentials, db

# ----------------------------
# Firebase Initialization
# ----------------------------
cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {
    "databaseURL": "https://last-cap-2932f-default-rtdb.europe-west1.firebasedatabase.app/"
})

# ----------------------------
# Function to upload JSON file
# ----------------------------
def upload_json_to_firebase(json_path, firebase_path="/"):
    """Upload JSON file to Firebase Realtime Database root or subpath."""
    
    # Load JSON from file
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reference to the target path
    ref = db.reference(firebase_path)

    # Write JSON structure exactly as is
    ref.set(data)

    print(f"Successfully uploaded JSON to '{firebase_path}'")

# ----------------------------
# Example Usage
# ----------------------------
if __name__ == "__main__":
    # The local JSON file to upload
    upload_json_to_firebase("data.json")  
    # Example to upload to subpath:
    # upload_json_to_firebase("data.json", "/traffic_data")

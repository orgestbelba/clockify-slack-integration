import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
CLOCKIFY_API_KEY = os.getenv("CLOCKIFY_API_KEY")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
WORKSPACE_ID = os.getenv("CLOCKIFY_WORKSPACE_ID")

# API endpoints
CLOCKIFY_TIME_OFF_URL = f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/time-off/requests"
SLACK_UPDATE_STATUS_URL = "https://slack.com/api/users.profile.set"
SLACK_LOOKUP_BY_EMAIL_URL = "https://slack.com/api/users.lookupByEmail"

# Get today's date
today = datetime.now(timezone.utc).date()

# Set time range for today
START_DATE = datetime.combine(today, datetime.min.time(), timezone.utc).isoformat()
END_DATE = datetime.combine(today, datetime.max.time(), timezone.utc).replace(microsecond=999999).isoformat()

# Payload for Clockify API
PAYLOAD = {
    "start": START_DATE,
    "end": END_DATE,
    "statuses": ["APPROVED"],  # Fetch only approved requests
    "userGroups": ["63ceed2d4464230f61549c02"],  # Employee userGroup
    "users": []  # Empty list means all users
}

# Mapping of policy names to Slack statuses
STATUS_MAP = {
    "Vacations": ("On Holiday", ":palm_tree:"),
    "Sick": ("Off Sick", ":face_with_thermometer:")
}

def get_time_off_requests():
    """Fetch approved time-off requests from Clockify."""
    headers = {
        "X-Api-Key": CLOCKIFY_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(CLOCKIFY_TIME_OFF_URL, headers=headers, data=json.dumps(PAYLOAD))
    if response.status_code == 200:
        data = response.json()
        requests_list = data.get("requests", [])

        if not requests_list:
            print("📢 No time-off requests found for today.")
            return []

        return [
            {
                "email": request.get("userEmail"),
                "name": request.get("userName"),
                "start": request.get("timeOffPeriod", {}).get("period", {}).get("start"),
                "end": request.get("timeOffPeriod", {}).get("period", {}).get("end"),
                "status": request.get("status", {}).get("statusType"),
                "policy_name": request.get("policyName", {})
            }
            for request in requests_list
        ]
    else:
        print(f"❌ Error fetching Clockify data: {response.status_code}, {response.text}")
        return []


def get_slack_user_id(email):
    """Find a Slack user ID using their email."""
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"email": email}

    response = requests.get(SLACK_LOOKUP_BY_EMAIL_URL, headers=headers, params=params)
    data = response.json()

    if data.get("ok"):
        return data["user"]["id"]
    else:
        print(f"⚠️ Could not find Slack user for {email}: {data.get('error')}")
        return None


def set_user_status(user_id, text, emoji, expiration_time):
    """Update Slack status for a given user ID with expiration time."""
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "user": user_id,
        "profile": {
            "status_text": text,
            "status_emoji": emoji,
            "status_expiration": expiration_time  # Unix timestamp for expiration
        }
    }

    response = requests.post(SLACK_UPDATE_STATUS_URL, json=payload, headers=headers)
    if response.status_code == 200 and response.json().get("ok"):
        print(f"✅ Slack status updated for user {user_id}: {text}")
    else:
        print(f"❌ Failed to update Slack status for {user_id}: {response.json()}")


def update_slack_status_for_time_off_users():
    """Fetch time-off requests and update Slack status for those users."""
    time_off_users = get_time_off_requests()

    if not time_off_users:
        print("📢 No users on leave today.")
        return

    print(f"🔄 Updating Slack status for {len(time_off_users)} users on leave...")

    for user in time_off_users:
        email = user["email"]
        policy_name = user["policy_name"]
        end_date = user["end"]

        # Convert end_date to Unix timestamp
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace("Z", "+00:00"))  # Handle Zulu time
            expiration_time = int(end_datetime.timestamp())  # Convert to Unix timestamp
        else:
            expiration_time = 0  # No expiration if end date is missing

        # Get status text and emoji based on policy name
        if policy_name in STATUS_MAP:
            status_text, status_emoji = STATUS_MAP[policy_name]
        else:
            print(f"⚠️ Unknown policy '{policy_name}' for {email}. Skipping status update.")
            continue

        # Get Slack user ID
        slack_user_id = get_slack_user_id(email)
        if slack_user_id:
            set_user_status(slack_user_id, status_text, status_emoji, expiration_time)


if __name__ == "__main__":
    update_slack_status_for_time_off_users()
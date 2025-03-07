import requests
import json
import boto3
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# AWS Secrets Manager settings
SECRET_NAME = "Clockify_Slack_Secrets"
REGION_NAME = "eu-north-1"

def get_secrets():
    """Retrieve secrets from AWS Secrets Manager (Key-Value Pairs)."""
    print("🔐 Fetching secrets from AWS Secrets Manager...")

    client = boto3.client("secretsmanager", region_name=REGION_NAME)
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        print("✅ Successfully retrieved secrets!")

        if "SecretString" in response:
            secret_dict = json.loads(response["SecretString"])
            return secret_dict
        else:
            raise ValueError("⚠ No SecretString found in AWS Secrets Manager response.")
    except Exception as e:
        print(f"❌ Error retrieving secrets: {e}")
        return {}

# Fetch secrets (Parsed as Key-Value Pairs)
secrets = get_secrets()
CLOCKIFY_API_KEY = secrets.get("CLOCKIFY_API_KEY")
SLACK_TOKEN = secrets.get("SLACK_TOKEN")
WORKSPACE_ID = secrets.get("CLOCKIFY_WORKSPACE_ID")

# API endpoints
CLOCKIFY_TIME_OFF_URL = f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/time-off/requests"
SLACK_UPDATE_STATUS_URL = "https://slack.com/api/users.profile.set"
SLACK_LOOKUP_BY_EMAIL_URL = "https://slack.com/api/users.lookupByEmail"

STATUS_MAP = {
    "Vacations": ("On Holiday", ":palm_tree:"),
    "Sick": ("Off Sick", ":face_with_thermometer:")
}

def get_time_off_requests():
    """Fetch approved time-off requests from Clockify."""
    print("🔍 Fetching approved time-off requests from Clockify...")

    today = datetime.now(timezone.utc).date()
    START_DATE = datetime.combine(today, datetime.min.time(), timezone.utc).isoformat()
    END_DATE = datetime.combine(today, datetime.max.time(), timezone.utc).replace(microsecond=999999).isoformat()

    payload = {
        "start": START_DATE,
        "end": END_DATE,
        "statuses": ["APPROVED"],
        "userGroups": ["63ceed2d4464230f61549c02"],  # Employee userGroup
        "users": []
    }

    headers = {"X-Api-Key": CLOCKIFY_API_KEY, "Content-Type": "application/json"}
    response = requests.post(CLOCKIFY_TIME_OFF_URL, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        return [
            {
                "email": req.get("userEmail"),
                "name": req.get("userName"),
                "start": req.get("timeOffPeriod", {}).get("period", {}).get("start"),
                "end": req.get("timeOffPeriod", {}).get("period", {}).get("end"),
                "policy_name": req.get("policyName", {})
            }
            for req in data.get("requests", [])
        ]
    else:
        print(f"❌ Error fetching Clockify data: {response.status_code}, {response.text}")
        return []

def get_slack_user_id(email):
    """Find a Slack user ID using their email."""
    print(f"🔍 Looking up Slack user ID for email: {email}")

    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"}
    response = requests.get(SLACK_LOOKUP_BY_EMAIL_URL, headers=headers, params={"email": email})

    data = response.json()
    if data.get("ok"):
        return data["user"]["id"]
    else:
        logging.warning(f"⚠ Unable to find Slack user for email: {email}")
        return None

def set_user_status(user_id, text, emoji, expiration_time):
    """Update Slack status for a given user ID."""
    print(f"📝 Updating Slack status for user {user_id} to '{text}' {emoji} (expires at {expiration_time})")

    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"}
    payload = {"user": user_id, "profile": {"status_text": text, "status_emoji": emoji, "status_expiration": expiration_time}}
    response = requests.post(SLACK_UPDATE_STATUS_URL, json=payload, headers=headers)

    if response.status_code == 200 and response.json().get("ok"):
        print(f"✅ Slack status updated for user {user_id}: {text}")
    else:
        logging.error(f"❌ Failed to update Slack status for {user_id}: {response.json()}")

def update_slack_status_for_time_off_users():
    """Fetch time-off requests and update Slack status for those users."""
    print("🚀 Updating Slack statuses for time-off users...")

    time_off_users = get_time_off_requests()
    print(f"🧑‍💼 Found {len(time_off_users)} users on leave today.")

    for user in time_off_users:
        email, policy_name, end_date = user["email"], user["policy_name"], user["end"]
        print(f"👤 Processing {email} with leave policy: {policy_name}")

        expiration_time = int(datetime.fromisoformat(end_date.replace("Z", "+00:00")).timestamp()) if end_date else 0

        if policy_name in STATUS_MAP:
            slack_user_id = get_slack_user_id(email)
            print(f"🔹 Slack User ID for {email}: {slack_user_id}")

            if slack_user_id:
                set_user_status(slack_user_id, *STATUS_MAP[policy_name], expiration_time)
            else:
                logging.warning(f"⚠ Skipping status update for {email} (Slack user ID not found)")

def lambda_handler(event, context):
    """AWS Lambda entry point."""
    print("✅ Lambda function started!")

    update_slack_status_for_time_off_users()

    print("✅ Lambda function completed!")
    return {"statusCode": 200, "body": "Lambda function completed successfully!"}
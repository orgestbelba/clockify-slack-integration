# Clockify Slack Integration

## Overview

The **Clockify Slack Integration** automates the process of updating Slack statuses based on approved time-off requests from Clockify. 
The solution determines when users are off and when they will return to work, adjusting their Slack statuses accordingly. 
This script is designed to run as a **daily job in AWS Lambda**.

## How It Works

1. Fetches **approved time-off requests** from Clockify.
2. Identifies the **start and end time** of each request.
3. Gets the **Slack user ID** based on their e-mail. 
4. Updates the **corresponding Slack statuses** based on availability. 
5. Runs **daily at 9 AM Europe Time** via **AWS Lambda** (scheduled through **EventBridge**).

## Running Locally

To run the script locally, you need a `.env` file containing the required credentials. Then, execute:

```bash
python main.py
```

## AWS Lambda Deployment

To deploy the script to **AWS Lambda**, follow these steps:

### 1. Create a package directory

```bash
mkdir package
```

### 2. Install dependencies

```bash
uv pip install --target ./package --requirements pyproject.toml
```

### 3. Copy the Lambda function script

```bash
cp lambda_function.py ./package/
```

### 4. Zip the package folder

```bash
cd package
zip -r ../deployment.zip .
```

Now, you can **upload `deployment.zip` to AWS Lambda**.

## AWS Lambda Setup

Currently, the **`clockify_slack_integration_test2` Lambda function** is created with the necessary **IAM policies** to access **AWS Secrets Manager**, where sensitive credentials are securely stored.

### Scheduled Execution

The Lambda function is triggered **every day at 9 AM CET** using **AWS EventBridge**.

## Environment Variables

The script requires a `.env` file (for local execution) or AWS Secrets Manager (for Lambda execution) with credentials for:

- **Clockify API**
- **Slack API**
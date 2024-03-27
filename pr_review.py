import requests
import os
import logging
import sys
from dotenv import load_dotenv
from openai import OpenAI
from urllib.parse import urlparse, parse_qs

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv("local.env")

def review_code_with_gpt4(code_diff, openai_api_key):
    """
    Sends the code diff to GPT-4 and receives feedback.
    """
    client = OpenAI(api_key=openai_api_key)
    prompt = (
        "Review the following GitHub PR code changes:\n\n"
        f"{code_diff}\n\n"
        "Provide detailed constructive feedback to improve the code given. "
        "When suggesting changes, please show the line before and after change."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return "Failed to get feedback from GPT-4."

def fetch_pr_diff(owner, repo, pr_number, github_token=None):
    """
    Fetches the PR diff from GitHub.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        logging.error(f"Failed to fetch PR details. Status Code: {response.status_code}")
        print(response.textw)
        return None

def filter_diff_based_on_extensions(diff, exclude_extensions):
    """
    Filters out diffs from files with specified extensions.
    """
    filtered_diff = []
    skip_chunk = False

    for line in diff.split("\n"):
        if line.startswith('diff --git'):
            skip_chunk = any(ext in line for ext in exclude_extensions)
        if not skip_chunk:
            filtered_diff.append(line)
        elif line == "":
            skip_chunk = False

    return "\n".join(filtered_diff)

def split_diff_and_review(code_diff, openai_api_key, max_chars=24000):
    """
    Splits the diff into chunks for review.
    """
    feedbacks = []
    chunk = ""

    for line in code_diff.split("\n"):
        if len(chunk) + len(line) + 1 > max_chars:
            feedback = review_code_with_gpt4(chunk, openai_api_key)
            feedbacks.append(feedback)
            chunk = line
        else:
            chunk += f"\n{line}"

    if chunk:
        feedback = review_code_with_gpt4(chunk, openai_api_key)
        feedbacks.append(feedback)

    return " ".join(feedbacks)

def main(pr_link):
    """
    Main function to process the PR link and print feedback.
    """
    parsed_url = urlparse(pr_link)
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) < 4 or path_parts[2] != "pull":
        logging.error("Invalid PR link format.")
        return

    owner, repo, _, pr_number = path_parts[:4]
    github_token = os.getenv("GITHUB_API_KEY")
    openai_api_key = os.getenv("OPEN_AI_API_KEY")

    logging.info(f"Fetching PR #{pr_number} diff from {owner}/{repo}...")
    pr_diff = fetch_pr_diff(owner, repo, pr_number, github_token)

    if pr_diff:
        logging.info("Processing diff code...")
        exclude_extensions = [".ipynb", ".md", ".lock"]  # Add more extensions as needed
        pr_diff_filtered = filter_diff_based_on_extensions(pr_diff, exclude_extensions)

        logging.info("Reviewing code diff...")
        feedback = split_diff_and_review(pr_diff_filtered, openai_api_key)
        print(feedback)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python pr_review.py <PR_LINK>")
        sys.exit(1)
    main(sys.argv[1])

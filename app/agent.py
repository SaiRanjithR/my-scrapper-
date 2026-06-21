# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

import datetime
import os
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import START, Workflow, node
from google.genai import types
from pydantic import BaseModel, Field

from app.tools import (
    DEFAULT_CHANNELS,
    get_youtube_uploads,
    render_designer_html,
    search_tavily,
    send_email_digest,
)

# Load local environment variables from .env
load_dotenv()

# Setup project and location credentials for Google Cloud or AI Studio
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not project_id or project_id == "your_gcp_project_id_here":
    try:
        import google.auth

        _, project_id = google.auth.default()
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    except Exception:
        pass

api_key = os.environ.get("GEMINI_API_KEY")

# If GOOGLE_GENAI_USE_VERTEXAI is already explicitly set (e.g. by CI/CD),
# respect that value and don't override it.
if "GOOGLE_GENAI_USE_VERTEXAI" not in os.environ:
    # Auto-detect: AIzaSy and AQ. prefixed keys are AI Studio keys
    if api_key and (api_key.startswith("AIzaSy") or api_key.startswith("AQ.")):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
    else:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
        if "GOOGLE_CLOUD_LOCATION" not in os.environ:
            os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

# Unset invalid placeholder key if it exists
if api_key and api_key == "your_api_key_here":
    del os.environ["GEMINI_API_KEY"]

# Ensure the genai SDK can find the API key
if api_key and os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "False":
    os.environ["GOOGLE_API_KEY"] = api_key



# 1. Define structured schemas for synthesis
class NewsItem(BaseModel):
    title: str = Field(description="Title of the news article or update")
    summary: str = Field(
        description="One-sentence executive summary highlighting the importance/impact"
    )
    source_url: str = Field(description="URL to the source article")
    image_url: str | None = Field(
        None, description="OpenGraph or preview image URL if available"
    )
    category: str = Field(
        description="Category (e.g. 'Frontier AI', 'Hardware & Semiconductors', 'Developer Tools', 'Tech Trends')"
    )


class VideoItem(BaseModel):
    title: str = Field(description="Title of the YouTube video")
    creator: str = Field(description="Name of the video creator/channel")
    video_url: str = Field(description="Direct watch link for the video")
    thumbnail_url: str = Field(description="YouTube thumbnail URL")
    published_at: str = Field(description="Upload timestamp")
    summary: str = Field(
        description="One-sentence summary of the video's core content and takeaways"
    )


class DigestPayload(BaseModel):
    date: str = Field(description="Current date in format 'Month DD, YYYY'")
    headline: str = Field(
        description="A catchy, premium headline summarizing today's key developments"
    )
    editorial_summary: str = Field(
        description="A short editorial paragraph summarizing the main compounding narratives over the last 96 hours."
    )
    news_items: list[NewsItem] = Field(
        description="List of selected high-signal tech/AI news updates (max 5)"
    )
    video_items: list[VideoItem] = Field(
        description="List of selected high-signal developer/creator video uploads (max 5)"
    )


# 2. Define Workflow Nodes


@node
def gather_data(node_input: Any) -> dict:
    """Gather news and creator video uploads looking back across 96 hours."""
    print("Starting news and video aggregation...")

    # Define broad tech/AI search queries
    queries = [
        "frontier LLM launch open source weights Hugging Face",
        "Nvidia GPU NPU semiconductor launch chip hardware news",
        "next-gen AI orchestration framework release multi-agent",
    ]

    # Collect Tavily search results
    tavily_results = []
    for q in queries:
        tavily_results.extend(search_tavily(q))

    # Deduplicate Tavily results by URL
    seen_urls = set()
    dedup_tavily = []
    for item in tavily_results:
        url = item.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            dedup_tavily.append(item)

    # Collect YouTube uploads from configured creators
    youtube_videos = []
    for name, channel_id in DEFAULT_CHANNELS.items():
        youtube_videos.extend(get_youtube_uploads(channel_id, name))

    print(
        f"Aggregated {len(dedup_tavily)} web articles and {len(youtube_videos)} creator videos."
    )
    return {"raw_news": dedup_tavily, "raw_videos": youtube_videos}


# Synthesizer Node uses Gemini model to filter, prioritize, and structure the data
synthesizer = LlmAgent(
    name="synthesizer",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are an elite, premium AI research assistant.
Your task is to analyze raw tech news articles and creator video uploads from the last 96 hours and select the absolute highest-signal updates.
Group the news into categories, write high-impact summaries, write a strong overall headline and a short editorial paragraph summarizing the key trends.
Follow the output schema strictly. Limit news items to a max of 5, and video items to a max of 5.""",
    output_schema=DigestPayload,
    output_key="digest",
)


@node
def render_html(ctx: Context, node_input: dict) -> str:
    """Render the structured digest into designer HTML."""
    # node_input is the output from the predecessor (synthesizer)
    # Since synthesizer has output_schema=DigestPayload, the output is a dict representing the payload.
    print("Rendering designer HTML...")
    html_content = render_designer_html(node_input)
    # Store html content in state for the next node or debugging
    return html_content


@node
def send_email(node_input: str) -> str:
    """Send the rendered HTML via SMTP or save it locally if credentials are not configured."""
    print("=" * 60)
    print("SEND EMAIL NODE REACHED")
    print(f"  HTML content length: {len(node_input) if node_input else 0}")
    print(f"  GOOGLE_GENAI_USE_VERTEXAI: {os.environ.get('GOOGLE_GENAI_USE_VERTEXAI')}")
    print("=" * 60)
    today_str = datetime.date.today().strftime("%B %d, %Y")
    success = send_email_digest(node_input, today_str)
    if success:
        return "Digest sent successfully."
    else:
        return "Failed to send digest."


# 3. Create the Workflow Graph
workflow = Workflow(
    name="antigravity_digest_workflow",
    edges=[
        (START, gather_data),
        (gather_data, synthesizer),
        (synthesizer, render_html),
        (render_html, send_email),
    ],
    description="Gathers tech/AI updates, synthesizes them with Gemini, and emails a premium brutalist-themed HTML digest under the name 'your mini scrapper'.",
)
root_agent = workflow

# 4. Instantiate the ADK App
app = App(
    root_agent=workflow,
    name="app",
)


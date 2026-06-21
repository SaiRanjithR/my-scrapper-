# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

DEFAULT_CHANNELS = {
    "ThePrimeagen": "UCuzc7KC124M15Z_97H_xSJA",
    "MatthewBerman": "UCy5znSnfS9F477XlE5S1tHA",
    "Sentdex": "UCfzlCWGWYyIQ0aLC5w78gXg",
    "WesRoth": "UCvG07XEqW5wT3yW3_pI2k5A",
    "YannicKilcher": "UCm9K318fM4g17T-M_c79n3A",
}


def search_tavily(query: str) -> list[dict]:
    """Search the web using Tavily with a 96-hour lookback."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key or api_key == "your_tavily_api_key_here":
        print("Tavily API key not configured or using placeholder.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "days": 4,  # strict 96-hour lookback
        "max_results": 5,
    }

    try:
        print(f"Searching Tavily for query: '{query}'")
        response = httpx.post(url, json=payload, timeout=20.0)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"Tavily search failed for '{query}': {e}")
        return []


def is_within_96h(published_date_str: str) -> bool:
    """Helper to check if a relative published date string is within the last 96 hours."""
    if not published_date_str:
        return False
    s = published_date_str.lower()
    # Minutes, hours, seconds, today, or yesterday are always within 96 hours
    if (
        "minute" in s
        or "hour" in s
        or "second" in s
        or "today" in s
        or "yesterday" in s
    ):
        return True
    if "day" in s:
        try:
            # e.g., "3 days ago" -> 3
            days = int(s.split()[0])
            return days <= 4  # 96 hours is exactly 4 days
        except Exception:
            return True
    return False


def get_youtube_uploads(channel_id: str, channel_name: str) -> list[dict]:
    """Fetch video uploads from a specific channel within the last 96 hours using Scrapingdog API."""
    api_key = os.environ.get("SCRAPINGDOG_API_KEY")
    if not api_key or api_key == "your_scrapingdog_api_key_here":
        print("Scrapingdog API key not configured or using placeholder.")
        return []

    url = "https://api.scrapingdog.com/youtube/search"
    params = {
        "api_key": api_key,
        "search_query": channel_name,
        "sp": "CAISAhAB",  # Sort by upload date
    }

    try:
        print(
            f"Fetching YouTube uploads for channel '{channel_name}' via Scrapingdog..."
        )
        response = httpx.get(url, params=params, timeout=20.0)
        response.raise_for_status()

        video_results = response.json().get("video_results", [])
        videos = []
        for item in video_results:
            channel_info = item.get("channel", {})
            channel_title = channel_info.get("name", "")

            # Verify the video is indeed from the target channel (case-insensitive sub-match)
            if channel_name.lower() not in channel_title.lower():
                continue

            published_date = item.get("published_date", "")
            if not is_within_96h(published_date):
                continue

            video_url = item.get("link", "")
            thumbnail_url = item.get("thumbnail", {}).get("static", "")
            if not thumbnail_url:
                # Extract fallback from video link
                # e.g., https://www.youtube.com/watch?v=XYZ -> XYZ
                video_id = ""
                if "v=" in video_url:
                    video_id = video_url.split("v=")[1].split("&")[0]
                if video_id:
                    thumbnail_url = (
                        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    )

            videos.append(
                {
                    "title": item.get("title", ""),
                    "creator": channel_title,
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "published_at": published_date,
                    "description": item.get("description", ""),
                }
            )

        print(f"Scrapingdog found {len(videos)} recent videos for {channel_name}.")
        return videos
    except Exception as e:
        print(f"Scrapingdog fetch failed for '{channel_name}': {e}")
        return []


def render_designer_html(payload: dict) -> str:
    """Render the gathered digest payload into a designer Brutalist off-white HTML email."""
    date_str = datetime.date.today().strftime("%B %d, %Y")
    headline = payload.get("headline", "Daily Tech Intel Briefing")
    editorial_summary = payload.get(
        "editorial_summary", "Aggregating critical updates."
    )

    news_items = payload.get("news_items", [])
    video_items = payload.get("video_items", [])

    # Generate news items HTML
    news_items_html = ""
    for item in news_items:
        title = item.get("title", "Untitled Update")
        summary = item.get("summary", "")
        url = item.get("source_url", "#")
        image_url = item.get("image_url")
        category = item.get("category", "Tech Update")

        image_html = ""
        if image_url:
            image_html = f'<img src="{image_url}" alt="Article Image" class="article-image" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">'

        fallback_box_html = (
            '<div class="fallback-image-text" style="display:none;">NEWS</div>'
        )
        if not image_url:
            fallback_box_html = (
                '<div class="fallback-image-text" style="display:block;">NEWS</div>'
            )

        news_items_html += f"""
        <div class="article-card">
            <span class="article-category">{category}</span>
            <h3 class="article-title"><a href="{url}" target="_blank">{title}</a></h3>
            <div class="article-body">
                <div class="article-text-container">
                    <div class="article-text">{summary}</div>
                    <div style="margin-top: 15px;">
                        <a href="{url}" target="_blank" class="action-link">READ ARTICLE</a>
                    </div>
                </div>
                <div class="article-image-wrapper">
                    <a href="{url}" target="_blank" style="display:block; width:100%; height:100%; text-decoration:none; text-align:center; display:flex; align-items:center; justify-content:center;">
                        {image_html}
                        {fallback_box_html}
                    </a>
                </div>
            </div>
        </div>
        """

    # Generate video items HTML
    video_items_html = ""
    for item in video_items:
        title = item.get("title", "Untitled Video")
        creator = item.get("creator", "Creator")
        url = item.get("video_url", "#")
        thumbnail_url = item.get("thumbnail_url")
        summary = item.get("summary", "")

        thumbnail_html = ""
        if thumbnail_url:
            thumbnail_html = f'<img src="{thumbnail_url}" alt="Video Thumbnail" class="video-thumbnail" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">'

        fallback_box_html = (
            '<div class="fallback-image-text" style="display:none;">VIDEO</div>'
        )
        if not thumbnail_url:
            fallback_box_html = (
                '<div class="fallback-image-text" style="display:block;">VIDEO</div>'
            )

        video_items_html += f"""
        <div class="video-card">
            <div class="video-thumbnail-wrapper">
                <a href="{url}" target="_blank" style="display:block; width:100%; height:100%; text-decoration:none;">
                    {thumbnail_html}
                    {fallback_box_html}
                    <div class="video-play-btn">&#9658;</div>
                </a>
            </div>
            <div class="video-info">
                <div>
                    <h3 class="video-title"><a href="{url}" target="_blank">{title}</a></h3>
                    <span class="video-creator">{creator}</span>
                    <div class="video-desc">{summary}</div>
                </div>
                <div style="margin-top: 10px;">
                    <a href="{url}" target="_blank" class="action-link">WATCH VIDEO</a>
                </div>
            </div>
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>your mini scrapper</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Inter:wght@400;500;600;700&display=swap');
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #F4F3EF;
            color: #1A1A1A;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            max-width: 680px;
            margin: 30px auto;
            background-color: #F4F3EF;
            border: 3px solid #1A1A1A;
            box-shadow: 8px 8px 0px #1A1A1A;
            overflow: hidden;
        }}
        .header {{
            background-color: #F4F3EF;
            border-bottom: 3px solid #1A1A1A;
            padding: 40px 35px 35px 35px;
            text-align: left;
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 40px;
            border-bottom: 1.5px solid #1A1A1A;
            padding-bottom: 15px;
        }}
        .logo {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #1A1A1A;
        }}
        .logo-sub {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 10px;
            font-weight: 500;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: #1A1A1A;
            background-color: #D4FF00;
            border: 1px solid #1A1A1A;
            padding: 2px 8px;
        }}
        .hero-title {{
            font-family: 'Oswald', 'Arial Narrow', 'Impact', sans-serif;
            margin: 0;
            color: #1A1A1A;
            font-size: 54px;
            font-weight: 700;
            letter-spacing: -1.5px;
            text-transform: uppercase;
            line-height: 0.9;
            margin-bottom: 25px;
        }}
        .header-badge {{
            display: inline-block;
            background-color: #1A1A1A;
            color: #F4F3EF;
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            padding: 4px 12px;
        }}
        .content {{
            padding: 35px;
        }}
        .editorial {{
            margin-bottom: 40px;
            padding: 25px;
            background-color: #FFFFFF;
            border: 2.5px solid #1A1A1A;
            box-shadow: 5px 5px 0px #1A1A1A;
        }}
        .editorial h2 {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 22px;
            font-weight: 700;
            text-transform: uppercase;
            color: #1A1A1A;
            margin-top: 0;
            margin-bottom: 15px;
            line-height: 1.2;
            letter-spacing: -0.5px;
        }}
        .editorial p {{
            line-height: 1.6;
            color: #333333;
            font-size: 14.5px;
            margin: 0;
        }}
        .dots-separator {{
            text-align: left;
            padding: 10px 0;
            margin: 25px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .dot {{
            background-color: #1A1A1A;
            border-radius: 50%;
            display: inline-block;
        }}
        .small-dot {{
            width: 8px;
            height: 8px;
        }}
        .large-dot {{
            width: 22px;
            height: 22px;
        }}
        .section-title {{
            font-family: 'Oswald', 'Arial Narrow', 'Impact', sans-serif;
            font-size: 26px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: -0.5px;
            color: #1A1A1A;
            margin-top: 45px;
            margin-bottom: 25px;
            text-align: left;
        }}
        .section-title span {{
            position: relative;
            display: inline-block;
            padding: 8px 24px;
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 60' preserveAspectRatio='none'><path d='M 10,30 C 10,10 230,5 230,30 C 230,55 15,58 10,35 C 8,25 40,8 210,12' style='fill:none;stroke:%23D4FF00;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;'/></svg>");
            background-repeat: no-repeat;
            background-size: 100% 100%;
        }}
        .article-card {{
            background-color: #FFFFFF;
            border: 2.5px solid #1A1A1A;
            box-shadow: 5px 5px 0px #1A1A1A;
            padding: 25px;
            margin-bottom: 30px;
            display: flex;
            flex-direction: column;
        }}
        .article-category {{
            align-self: flex-start;
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: #1A1A1A;
            background-color: #D4FF00;
            border: 1.5px solid #1A1A1A;
            padding: 2px 8px;
            margin-bottom: 15px;
        }}
        .article-title {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 22px;
            font-weight: 700;
            color: #1A1A1A;
            margin: 0 0 15px 0;
            text-transform: uppercase;
            line-height: 1.15;
            letter-spacing: -0.5px;
        }}
        .article-title a {{
            color: #1A1A1A;
            text-decoration: none;
        }}
        .article-title a:hover {{
            color: #555555;
            text-decoration: underline;
        }}
        .article-body {{
            display: flex;
            flex-direction: row;
            gap: 20px;
        }}
        .article-text-container {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .article-text {{
            font-size: 14px;
            color: #333333;
            line-height: 1.6;
        }}
        .action-link {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            color: #1A1A1A;
            text-decoration: none;
            border-bottom: 3px solid #1A1A1A;
            padding-bottom: 2px;
            display: inline-block;
            letter-spacing: 0.5px;
        }}
        .action-link:hover {{
            color: #555555;
            border-bottom-color: #555555;
        }}
        .article-image-wrapper {{
            width: 140px;
            height: 95px;
            border: 2px solid #1A1A1A;
            box-shadow: 3px 3px 0px #1A1A1A;
            overflow: hidden;
            flex-shrink: 0;
            background-color: #F4F3EF;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .article-image {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .fallback-image-text {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 12px;
            color: #1A1A1A;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .video-card {{
            background-color: #FFFFFF;
            border: 2.5px solid #1A1A1A;
            box-shadow: 5px 5px 0px #1A1A1A;
            padding: 25px;
            margin-bottom: 30px;
            display: flex;
            flex-direction: row;
            gap: 20px;
        }}
        .video-thumbnail-wrapper {{
            width: 180px;
            height: 105px;
            border: 2px solid #1A1A1A;
            box-shadow: 3px 3px 0px #1A1A1A;
            overflow: hidden;
            position: relative;
            flex-shrink: 0;
            background-color: #F4F3EF;
        }}
        .video-thumbnail {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .video-play-btn {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 36px;
            height: 36px;
            background-color: #D4FF00;
            border: 2px solid #1A1A1A;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #1A1A1A;
            font-size: 14px;
            font-weight: bold;
        }}
        .video-info {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .video-title {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 19px;
            font-weight: 700;
            color: #1A1A1A;
            margin: 0 0 5px 0;
            text-transform: uppercase;
            line-height: 1.2;
            letter-spacing: -0.5px;
        }}
        .video-title a {{
            color: #1A1A1A;
            text-decoration: none;
        }}
        .video-title a:hover {{
            color: #555555;
            text-decoration: underline;
        }}
        .video-creator {{
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 12px;
            color: #1A1A1A;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 10px;
            display: inline-block;
            background-color: #F4F3EF;
            padding: 2px 8px;
            border: 1px solid #1A1A1A;
            align-self: flex-start;
        }}
        .video-desc {{
            font-size: 13.5px;
            color: #333333;
            line-height: 1.5;
            margin-bottom: 10px;
        }}
        .footer {{
            text-align: center;
            padding: 35px 20px;
            border-top: 3px solid #1A1A1A;
            font-family: 'Oswald', 'Arial Narrow', sans-serif;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #555555;
            background-color: #FFFFFF;
        }}
        @media (max-width: 600px) {{
            .article-body {{
                flex-direction: column-reverse;
            }}
            .article-image-wrapper {{
                width: 100%;
                height: 150px;
                margin-bottom: 10px;
            }}
            .video-card {{
                flex-direction: column;
            }}
            .video-thumbnail-wrapper {{
                width: 100%;
                height: 180px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div class="logo">your mini scrapper</div>
                <div class="logo-sub">one stop solution</div>
            </div>
            <h1 class="hero-title">
                YOUR MINI<br>&nbsp;&nbsp;SCRAPPER
            </h1>
            <div class="header-badge">PREMIUM TECH DIGEST &bull; {date_str}</div>
        </div>
        <div class="content">
            <div class="editorial">
                <h2>{headline}</h2>
                <p>{editorial_summary}</p>
            </div>

            <div class="dots-separator">
                <span class="dot small-dot"></span>
                <span class="dot large-dot"></span>
            </div>

            <div class="section-title">
                <span>Machine Intelligence & Tech</span>
            </div>
            {news_items_html}

            <div class="dots-separator">
                <span class="dot small-dot"></span>
                <span class="dot large-dot"></span>
            </div>

            <div class="section-title">
                <span>Developer Streams</span>
            </div>
            {video_items_html}
        </div>
        <div class="footer">
            Your Mini Scrapper V2.0 &bull; Automated Research Asset &bull; 96H Rolling Scan
        </div>
    </div>
</body>
</html>
"""
    return html_template


def send_email_digest(html_content: str, date_str: str) -> bool:
    """Send the generated digest email using Gmail SMTP and app passwords."""
    # Always save the HTML locally for review and verification
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
    )
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(
        output_dir, f"digest_{datetime.date.today().isoformat()}.html"
    )
    try:
        with open(file_path, "w") as f:
            f.write(html_content)
        print(f"Saved generated HTML digest locally to: {file_path}")
    except Exception as e:
        print(f"Failed to save local copy of digest: {e}")

    sender_email = os.environ.get("SENDER_EMAIL")
    recipient_email = os.environ.get("RECIPIENT_EMAIL")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if (
        not all([sender_email, recipient_email, app_password])
        or sender_email == "your_sender_gmail_here@gmail.com"
    ):
        print(
            "Gmail SMTP credentials or email placeholders detected. Skipping SMTP send."
        )
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Antigravity AI & Tech Premium Digest - {date_str}"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    part_html = MIMEText(html_content, "html")
    msg.attach(part_html)

    try:
        print(f"Connecting to Gmail SMTP to send email to {recipient_email}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"Successfully sent digest email to {recipient_email}")
        return True
    except Exception as e:
        print(f"Failed to send email via SMTP: {e}")
        return False

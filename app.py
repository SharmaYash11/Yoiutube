import streamlit as st
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import altair as alt
import requests
from urllib.parse import urlparse, parse_qs
import isodate

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="YouTube Analytics Dashboard",
    layout="wide"
)

# ---------------- API KEY ----------------

API_KEY = st.secrets["API_KEY"]

# ---------------- SESSION STATE ----------------

if "channel_data" not in st.session_state:
    st.session_state["channel_data"] = None

if "videos_df" not in st.session_state:
    st.session_state["videos_df"] = None

if "top_videos" not in st.session_state:
    st.session_state["top_videos"] = None

if "comments_df" not in st.session_state:
    st.session_state["comments_df"] = None

# ---------------- SENTIMENT ANALYZER ----------------

analyzer = SentimentIntensityAnalyzer()

# ---------------- HELPERS ----------------

def extract_video_id(url):

    query = urlparse(url)

    if query.hostname == "youtu.be":
        return query.path[1:]

    if query.hostname in ["www.youtube.com", "youtube.com"]:
        return parse_qs(query.query).get("v", [None])[0]

    return None

# ---------------------------------------------------

def get_channel_id_from_video(video_id):

    print("CHANNEL ID API CALLED")

    url = "https://www.googleapis.com/youtube/v3/videos"

    params = {
        "part": "snippet",
        "id": video_id,
        "key": API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    data = response.json()

    return data["items"][0]["snippet"]["channelId"]

# ---------------------------------------------------
@st.cache_data(ttl=3600)
def get_channel_details(channel_id):

    print("CHANNEL DETAILS API CALLED")

    url = "https://www.googleapis.com/youtube/v3/channels"

    params = {
        "part": "snippet,statistics,contentDetails",
        "id": channel_id,
        "key": API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    data = response.json()

    item = data["items"][0]

    return {

        "channel_name":
            item["snippet"]["title"],

        "subscribers":
            int(
                item["statistics"].get(
                    "subscriberCount",
                    0
                )
            ),

        "views":
            int(
                item["statistics"].get(
                    "viewCount",
                    0
                )
            ),

        "videos":
            int(
                item["statistics"].get(
                    "videoCount",
                    0
                )
            ),

        "uploads_playlist":
            item["contentDetails"][
                "relatedPlaylists"
            ]["uploads"]
    }

# ---------------------------------------------------
@st.cache_data(ttl=3600)
def get_recent_videos(
    playlist_id,
    max_results=50
):

    print("RECENT VIDEOS API CALLED")

    url = "https://www.googleapis.com/youtube/v3/playlistItems"

    params = {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": max_results,
        "key": API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    data = response.json()

    videos = []

    for item in data["items"]:

        videos.append({

            "video_id":
                item["snippet"][
                    "resourceId"
                ]["videoId"],

            "title":
                item["snippet"]["title"]

        })

    return videos

# ---------------------------------------------------

def parse_duration(duration):

    total_seconds = int(
        isodate.parse_duration(
            duration
        ).total_seconds()
    )

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    return f"{minutes}m {seconds}s"

# ---------------------------------------------------
@st.cache_data(ttl=3600)
def get_video_stats(video_ids):

    print("VIDEO STATS API CALLED")

    url = "https://www.googleapis.com/youtube/v3/videos"

    params = {

        "part":
            "snippet,statistics,contentDetails",

        "id":
            ",".join(video_ids),

        "key":
            API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    data = response.json()

    video_data = []

    for item in data["items"]:

        stats = item["statistics"]

        snippet = item["snippet"]

        content = item["contentDetails"]

        views = int(
            stats.get("viewCount", 0)
        )

        likes = int(
            stats.get("likeCount", 0)
        )

        comments = int(
            stats.get("commentCount", 0)
        )

        engagement = round(
            ((likes + comments) / views),
            4
        ) if views > 0 else 0

        video_data.append({

            "video_id":
                item["id"],

            "Title":
                snippet["title"],

            "Views":
                views,

            "Likes":
                likes,

            "Comments":
                comments,

            "Published":
                snippet["publishedAt"][:10],

            "Duration":
                parse_duration(
                    content["duration"]
                ),

            "Engagement":
                engagement
        })

    return video_data

# ---------------------------------------------------

def get_video_comments(
    video_id,
    order_type
):

    print("COMMENTS API CALLED")

    url = "https://www.googleapis.com/youtube/v3/commentThreads"

    params = {

        "part":
            "snippet",

        "videoId":
            video_id,

        "maxResults":
            50,

        "order":
            order_type,

        "textFormat":
            "plainText",

        "key":
            API_KEY
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    data = response.json()

    comments_data = []

    for item in data["items"]:

        snippet = item[
            "snippet"
        ]["topLevelComment"]["snippet"]

        comments_data.append({

            "User":
                snippet.get(
                    "authorDisplayName"
                ),

            "Comment":
                snippet.get(
                    "textDisplay"
                ),

            "Likes":
                snippet.get(
                    "likeCount",
                    0
                ),

            "Replies":
                item["snippet"].get(
                    "totalReplyCount",
                    0
                ),

            "Date":
                snippet.get(
                    "publishedAt",
                    ""
                )[:10]
        })

    return comments_data

# ---------------------------------------------------

def get_sentiment(text):

    score = analyzer.polarity_scores(
        text
    )["compound"]

    if score >= 0.05:
        return "Positive"

    elif score <= -0.05:
        return "Negative"

    else:
        return "Neutral"

# ===================================================
# ---------------------- UI -------------------------
# ===================================================

st.title("📺 YouTube Analytics Dashboard")

video_url = st.text_input(
    "Enter YouTube Video URL"
)

analyze_button = st.button(
    "Analyze Channel"
)

# ===================================================
# ----------- CHANNEL ANALYSIS SECTION --------------
# ===================================================

if analyze_button and video_url:

    try:

        # STEP 1
        video_id = extract_video_id(
            video_url
        )

        # STEP 2
        channel_id = get_channel_id_from_video(
            video_id
        )

        # STEP 3
        channel_data = get_channel_details(
            channel_id
        )

        # STEP 4
        recent_videos = get_recent_videos(
            channel_data["uploads_playlist"]
        )

        video_ids = [

            v["video_id"]

            for v in recent_videos
        ]

        # STEP 5
        stats_data = get_video_stats(
            video_ids
        )

        videos_df = pd.DataFrame(
            stats_data
        )

        # STEP 6
        top_videos = videos_df.sort_values(
            by="Views",
            ascending=False
        ).head(10)

        top_videos = top_videos.reset_index(
            drop=True
        )

        # STEP 7
        st.session_state["channel_data"] = (
            channel_data
        )

        st.session_state["videos_df"] = (
            videos_df
        )

        st.session_state["top_videos"] = (
            top_videos
        )

        # RESET OLD COMMENTS
        st.session_state["comments_df"] = None

    except Exception as e:

        st.error(
            f"Something went wrong: {e}"
        )

# ===================================================
# ---------------- DISPLAY DASHBOARD ----------------
# ===================================================

if st.session_state["channel_data"] is not None:

    channel_data = st.session_state[
        "channel_data"
    ]

    videos_df = st.session_state[
        "videos_df"
    ]

    top_videos = st.session_state[
        "top_videos"
    ]

    # ---------------- AVERAGES ----------------

    avg_likes = int(
        videos_df["Likes"].mean()
    )

    avg_comments = int(
        videos_df["Comments"].mean()
    )

    # ---------------- KPI BOXES ----------------

    labels = [

        "Channel Name",

        "Subscribers",

        "Total Videos",

        "Total Views",

        "Avg Likes",

        "Avg Comments"
    ]

    values = [

        channel_data["channel_name"],

        f"{channel_data['subscribers']:,}",

        f"{channel_data['videos']:,}",

        f"{channel_data['views']:,}",

        f"{avg_likes:,}",

        f"{avg_comments:,}"
    ]

    cols = st.columns(6)

    BOX_HEIGHT = 120

    for col, label, value in zip(
        cols,
        labels,
        values
    ):

        with col:

            st.markdown(
                f"""
                <div style='
                    background-color: black;
                    height: {BOX_HEIGHT}px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-size: 18px;
                    font-weight: bold;
                    text-align: center;
                    padding: 10px;
                '>
                    {value}
                </div>

                <div style='
                    text-align: center;
                    margin-top: 8px;
                    font-size: 16px;
                    font-weight: 600;
                '>
                    {label}
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ---------------- TOP VIDEOS ----------------

    st.subheader(
        "🔥 Top 10 Performing Recent Videos"
    )

    st.caption(
        "Insights are based on the latest 50 uploaded videos."
    )

    st.dataframe(
        top_videos,
        use_container_width=True
    )

    # ===================================================
    # -------------- COMMENT ANALYSIS -------------------
    # ===================================================

    st.subheader(
        "🎯 Analyze Video Comments"
    )

    selected_video = st.selectbox(

        "Select a Video",

        top_videos["Title"].tolist()
    )

    comment_order = st.radio(

        "Comment Type",

        ["relevance", "time"],

        horizontal=True
    )

    analyze_comments = st.button(
        "Analyze Comments"
    )

    # ===================================================
    # ----------- RUN COMMENT ANALYSIS ------------------
    # ===================================================

    if analyze_comments:

        selected_row = top_videos[
            top_videos["Title"]
            == selected_video
        ].iloc[0]

        selected_video_id = selected_row[
            "video_id"
        ]

        comments_data = get_video_comments(
            selected_video_id,
            comment_order
        )

        comments_df = pd.DataFrame(
            comments_data
        )

        comments_df["Sentiment"] = (
            comments_df["Comment"].apply(
                get_sentiment
            )
        )

        st.session_state["comments_df"] = (
            comments_df
        )

# ===================================================
# -------------- DISPLAY COMMENTS -------------------
# ===================================================

if st.session_state["comments_df"] is not None:

    comments_df = st.session_state[
        "comments_df"
    ]

    sentiment_counts = (

        comments_df["Sentiment"]

        .value_counts(normalize=True)

        .mul(100)

        .round(1)

        .reset_index()
    )

    sentiment_counts.columns = [

        "Sentiment",

        "Percentage"
    ]

    chart = alt.Chart(
        sentiment_counts
    ).mark_bar().encode(

        x=alt.X(
            "Percentage:Q"
        ),

        y=alt.Y(
            "Sentiment:N",
            sort="-x"
        )

    ).properties(

        width=500,

        height=250
    )

    col1, col2 = st.columns([1, 1])

    with col1:

        st.altair_chart(
            chart,
            use_container_width=True
        )

    st.dataframe(
        comments_df,
        use_container_width=True
    )

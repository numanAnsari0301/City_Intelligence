from dotenv import load_dotenv

load_dotenv()

import os

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage

from agent import (
    DEFAULT_MODEL,
    build_agent as _build_agent,
    get_weather_details,
    message_text,
)

# ─────────────────────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mr. Mausam Khabri – City Assistant",
    page_icon="🧭",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────
# Agent (cached so it isn't rebuilt on every Streamlit rerun)
# ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def build_agent(model_name: str):
    return _build_agent(model_name)

def run_agent(agent, history: list[dict]):
    """Run the agent using only recent conversation history."""

    # Keep only the latest 6 messages
    recent_history = history[-6:]

    sent = [
        {
            "role": m["role"],
            "content": m["content"],
        }
        for m in recent_history
    ]

    result = agent.invoke({"messages": sent})

    new_messages = result["messages"][len(sent):]

    tools_used = []

    for msg in new_messages:

        if isinstance(msg, AIMessage) and msg.tool_calls:

            for call in msg.tool_calls:

                city = call["args"].get("city", "")

                tools_used.append(
                    {
                        "tool": call["name"],
                        "city": city,
                    }
                )

        elif isinstance(msg, ToolMessage):

            if message_text(msg.content).startswith("Error"):

                if tools_used:
                    tools_used[-1]["failed"] = True

    final = next(
        (
            message_text(m.content)
            for m in reversed(new_messages)
            if isinstance(m, AIMessage)
            and message_text(m.content).strip()
        ),
        "I couldn't put together an answer. Try asking again.",
    )

    return final, tools_used

# ─────────────────────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink: #12222f;
  --muted: #5d6f7c;
  --paper: #eef3f6;
  --card: #ffffff;
  --line: #d3dee5;
  --blue: #1f5fbf;
  --amber: #c98200;
  --red: #b3372f;
}

html, body, [class*="css"], .stApp {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
  color: var(--ink);
}
.stApp { background: var(--paper); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 760px; }

/* Masthead */
.masthead h1 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 3rem;
  line-height: 1.02;
  letter-spacing: -0.03em;
  margin: 0 0 .5rem 0;
  color: var(--ink);
}
.masthead p {
  font-size: 1.05rem;
  color: var(--muted);
  margin: 0 0 1.6rem 0;
  max-width: 34rem;
}

/* Suggestion buttons */
div[data-testid="stButton"] > button {
  width: 100%;
  text-align: left;
  justify-content: flex-start;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink);
  padding: .8rem 1rem;
  font-weight: 500;
  transition: border-color .15s, box-shadow .15s;
}
div[data-testid="stButton"] > button:hover {
  border-color: var(--blue);
  color: var(--blue);
}
div[data-testid="stButton"] > button:focus-visible {
  outline: 3px solid rgba(31,95,191,.35);
  outline-offset: 2px;
}

/* Chat */
[data-testid="stChatMessage"] {
  background: transparent;
  padding: .6rem 0;
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li { font-size: 1rem; line-height: 1.6; }

/* Tool trace chips (static ones: news, failed) */
.trace { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .4rem; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  font-size: .82rem;
  font-weight: 500;
  padding: .2rem .7rem;
  border-radius: 999px;
  background: var(--card);
  border: 1px solid var(--line);
}
.chip::before {
  content: "";
  width: .5rem;
  height: .5rem;
  border-radius: 50%;
  background: var(--dot, var(--muted));
}
.chip.news { --dot: var(--amber); }
.chip.failed { --dot: var(--red); color: var(--red); }

/* Clickable weather chips (Streamlit buttons with keys starting "chip_") */
[class*="st-key-chip_"] button {
  width: auto;
  min-height: 0;
  padding: .2rem .8rem;
  border-radius: 999px;
  font-size: .82rem;
  gap: .35rem;
}
[class*="st-key-chip_"] button svg,
[class*="st-key-chip_"] button span[data-testid="stIconMaterial"] { color: var(--blue); }

/* Weather dialog */
[data-testid="stMetricValue"] { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; }
.wx-temp {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 3.4rem;
  line-height: 1;
  letter-spacing: -0.03em;
}
.wx-desc { color: var(--muted); margin: .3rem 0 1rem 0; font-size: 1.05rem; }

/* Input */
[data-testid="stChatInput"] {
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--card);
}

/* Sidebar */
section[data-testid="stSidebar"] { background: #e2eaef; border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] h3 {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
}
.status-row { font-size: .9rem; margin: .15rem 0; }
.dot { display:inline-block; width:.6rem; height:.6rem; border-radius:50%; margin-right:.5rem; }
.dot.ok { background:#2a8a4a; }
.dot.bad { background:var(--red); }

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
@media (max-width: 640px) {
  .masthead h1 { font-size: 2.3rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []  # [{role, content, tools?}]
if "queued" not in st.session_state:
    st.session_state.queued = None


def queue_prompt(text: str):
    st.session_state.queued = text


def clear_chat():
    st.session_state.history = []


@st.cache_data(ttl=600, show_spinner=False)
def cached_weather(city: str) -> dict:
    """Cache for 10 minutes so re-opening a chip doesn't burn API calls."""
    return get_weather_details(city)


def uv_level(uv) -> tuple[str, str]:
    if uv is None:
        return "Not available", ""
    if uv < 3:
        return "Low", "No protection needed for most people."
    if uv < 6:
        return "Moderate", "Wear sunglasses and sunscreen if outside for long."
    if uv < 8:
        return "High", "Use sunscreen and seek shade around midday."
    if uv < 11:
        return "Very high", "Cover up, use SPF 30+, and avoid the midday sun."
    return "Extreme", "Avoid being outside around midday."


def fmt(value, unit="", digits=0):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}{unit}" if digits else f"{round(value)}{unit}"


@st.dialog("Weather details")
def weather_dialog(city: str):
    with st.spinner("Getting the latest readings…"):
        d = cached_weather(city)

    if "error" in d:
        st.error(f"Couldn't load weather for {city}. {d['error']}")
        return

    place = f"{d['name']}, {d['country']}" if d["country"] else d["name"]
    st.markdown(f"**{place}**")
    st.markdown(
        f'<div class="wx-temp">{fmt(d["temp"], "°C")}</div>'
        f'<div class="wx-desc">{d["description"]}. Feels like {fmt(d["feels_like"], "°C")}.</div>',
        unsafe_allow_html=True,
    )

    wind = fmt(d["wind_kmh"], " km/h", 1)
    if d["wind_dir"]:
        wind += f" {d['wind_dir']}"

    rows = [
        [
            ("Humidity", fmt(d["humidity"], "%")),
            ("Wind", wind),
            ("Wind gusts", fmt(d["wind_gust_kmh"], " km/h", 1)),
        ],
        [
            ("Pressure", fmt(d["pressure"], " hPa")),
            ("Visibility", fmt(d["visibility_km"], " km", 1)),
            ("Cloud cover", fmt(d["clouds"], "%")),
        ],
        [
            ("Today's low", fmt(d["temp_min"], "°C")),
            ("Today's high", fmt(d["temp_max"], "°C")),
            ("Sunrise / sunset", f"{d['sunrise']} / {d['sunset']}"),
        ],
    ]
    for row in rows:
        cols = st.columns(3)
        for col, (label, value) in zip(cols, row):
            col.metric(label, value)

    level, advice = uv_level(d["uv_now"])
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("UV index now", fmt(d["uv_now"], "", 1), level, delta_color="off")
    c2.metric("UV index today (max)", fmt(d["uv_max"], "", 1), uv_level(d["uv_max"])[0], delta_color="off")
    if advice:
        st.caption(advice)
    st.caption(f"Local time in {d['name']}: {d['updated']}. Data from OpenWeather and Open-Meteo.")


def render_trace(tools_used: list[dict], uid: int):
    """Weather lookups become clickable chips that open a details dialog;
    news lookups and failures stay as static chips."""
    if not tools_used:
        return

    seen, weather_cities, static = set(), [], []
    for t in tools_used:
        key = (t["tool"], t["city"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        if t["tool"] == "get_weather" and t["city"] and not t.get("failed"):
            weather_cities.append(t["city"])
        else:
            static.append(t)

    for start in range(0, len(weather_cities), 3):
        cols = st.columns(3)
        for offset, city in enumerate(weather_cities[start : start + 3]):
            with cols[offset]:
                if st.button(
                    f"Weather in {city}",
                    key=f"chip_{uid}_{start + offset}",
                    icon=":material/partly_cloudy_day:",
                    help="Open full weather details",
                ):
                    weather_dialog(city)

    labels = {"get_weather": "Checked weather", "get_news": "Read news"}
    chips = []
    for t in static:
        verb = labels.get(t["tool"], t["tool"])
        text = f"{verb} for {t['city']}" if t["city"] else verb
        if t.get("failed"):
            chips.append(f'<span class="chip failed">Couldn\'t complete: {text.lower()}</span>')
        else:
            chips.append(f'<span class="chip news">{text}</span>')
    if chips:
        st.markdown(f'<div class="trace">{"".join(chips)}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    model_name = st.text_input("Gemini model", value=DEFAULT_MODEL)

    st.markdown("### Connections")
    keys = {
        "Google (Gemini)": "GOOGLE_API_KEY",
        "OpenWeather": "OPENWEATHER_API_KEY",
        "Tavily": "TAVILY_API_KEY",
    }
    missing = []
    for label, env in keys.items():
        ok = bool(os.getenv(env))
        if not ok:
            missing.append(env)
        st.markdown(
            f'<div class="status-row"><span class="dot {"ok" if ok else "bad"}"></span>'
            f'{label}: {"connected" if ok else f"add {env} to .env"}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Conversation")
    st.button("Clear chat", on_click=clear_chat, disabled=not st.session_state.history)

# ─────────────────────────────────────────────────────────────
# Masthead
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="masthead">
  <h1>Mr. Mausam Khabri</h1>
  <p>Live weather and local news for any city. Ask in plain language.</p>
</div>
""",
    unsafe_allow_html=True,
)

prompt = st.chat_input("Ask about a city, like “News in Bhopal”")
if st.session_state.queued:
    prompt = st.session_state.queued
    st.session_state.queued = None

# Welcome suggestions (only before the first message)
welcome = st.empty()
if not st.session_state.history and not prompt:
    with welcome.container():
        suggestions = [
            "What's the weather in Delhi right now?",
            "Latest news in Bhopal",
            "Weather and news for Mumbai",
            "Compare the weather in Deoria and Lucknow",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            cols[i % 2].button(s, key=f"sugg_{i}", on_click=queue_prompt, args=(s,))

# ─────────────────────────────────────────────────────────────
# Chat history
# ─────────────────────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.history):
    avatar = "🧭" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_trace(msg.get("tools", []), idx)

# ─────────────────────────────────────────────────────────────
# Handle a new message
# ─────────────────────────────────────────────────────────────
if prompt:
    welcome.empty()
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🧭"):
        if missing:
            reply = (
                "I can't answer yet. Add these keys to your `.env` file and reload: "
                + ", ".join(f"`{m}`" for m in missing)
                + "."
            )
            tools_used = []
            st.markdown(reply)
        else:
            try:
                with st.spinner("Checking the city…"):
                    agent = build_agent(model_name.strip() or DEFAULT_MODEL)
                    reply, tools_used = run_agent(agent, st.session_state.history)
                st.markdown(reply)
                render_trace(tools_used, len(st.session_state.history))
            except Exception as e:
                tools_used = []
                reply = (
                    f"Something went wrong while contacting the model: `{e}`. "
                    "Check the model name in Settings and your API keys, then try again."
                )
                st.error(reply)

    st.session_state.history.append(
        {"role": "assistant", "content": reply, "tools": tools_used}
    )
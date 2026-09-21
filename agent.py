from dotenv import load_dotenv

load_dotenv()

import os
from datetime import datetime, timedelta, timezone

import requests
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient

DEFAULT_MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """You are Mr. Mausam Khabri.

You ONLY answer questions about:
- weather
- local news

Use get_weather for weather questions.
Use get_news for news questions.
Use both tools when the user asks for both.

Do not use unnecessary tools.
Do not guess information.
For unrelated questions, reply exactly:
"Sorry, I can only help with weather and local news-related questions."
"""

# 1. Weather tool
@tool
def get_weather(city: str) -> str:
    """Get Current weather of a city"""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric"
    )
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except requests.RequestException as e:
        return f"Error : Could not reach weather service ({e})"

    if str(data.get("cod")) != "200":
        return f"Error : {data.get('message', 'Could not fetch weather')}"

    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]
    return f"weather in {city}: {desc},{temp}°C"


# 2. Tavily news tool
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) 
 
@tool
def get_news(city: str) -> str:
    """Get the latest news of the city in bullet points
    Input should be city name like 'Bhopal', 'Deoria',etc"""
   
    query = f"latest news in {city}"

    try:
        response = tavily_client.search(
            query=query, search_depth="basic", max_results=3
        )
    except Exception as e:
        return f"Error : Could not fetch news ({e})"

    results = response.get("results", [])
    if not results:
        return f"No recent news found for {city}"

    formatted = f"Latest News for {city}: \n\n"
    for i, article in enumerate(results, 1):
        formatted += f"{i}. {article['title']}\n"
        formatted += f" {article['url']}\n\n"
    return formatted


def compass(deg) -> str:
    """Wind direction in degrees -> N, NE, E ..."""
    if deg is None:
        return ""
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return points[int((deg + 22.5) % 360 // 45)]


def get_weather_details(city: str) -> dict:
    """Full weather report for the UI (not an agent tool).

    Uses OpenWeather for the current conditions and Open-Meteo (free, no key)
    for the UV index, because OpenWeather's free plan doesn't include UV.
    Returns {"error": "..."} if the city can't be found or a service is down.
    "
    """
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": os.getenv("OPENWEATHER_API_KEY"), "units": "metric"},
            timeout=5,
        )
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        return {"error": f"Could not reach the weather service ({e})."}

    if str(data.get("cod")) != "200":
        return {"error": str(data.get("message", "Could not fetch weather")).capitalize() + "."}

    main = data.get("main", {})
    wind = data.get("wind", {})
    sys_ = data.get("sys", {})
    coord = data.get("coord", {})
    tz = timezone(timedelta(seconds=data.get("timezone", 0)))

    def clock(ts):
        return datetime.fromtimestamp(ts, tz).strftime("%I:%M %p").lstrip("0") if ts else "-"

    details = {
        "name": data.get("name", city),
        "country": sys_.get("country", ""),
        "description": data["weather"][0]["description"].capitalize(),
        "temp": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "temp_min": main.get("temp_min"),
        "temp_max": main.get("temp_max"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "wind_kmh": round(wind.get("speed", 0) * 3.6, 1),
        "wind_gust_kmh": round(wind["gust"] * 3.6, 1) if wind.get("gust") else None,
        "wind_dir": compass(wind.get("deg")),
        "visibility_km": round(data["visibility"] / 1000, 1) if "visibility" in data else None,
        "clouds": data.get("clouds", {}).get("all"),
        "sunrise": clock(sys_.get("sunrise")),
        "sunset": clock(sys_.get("sunset")),
        "updated": datetime.now(tz).strftime("%I:%M %p").lstrip("0"),
        "uv_now": None,
        "uv_max": None,
    }

    # UV index: optional, so a failure here never breaks the rest of the report
    if coord:
        try:
            uv = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": coord["lat"],
                    "longitude": coord["lon"],
                    "current": "uv_index",
                    "daily": "uv_index_max",
                    "forecast_days": 1,
                    "timezone": "auto",
                },
                timeout=5,
            ).json()
            details["uv_now"] = uv.get("current", {}).get("uv_index")
            daily = uv.get("daily", {}).get("uv_index_max") or [None]
            details["uv_max"] = daily[0]
        except (requests.RequestException, ValueError):
            pass

    return details


TOOLS = [get_news, get_weather]


def build_agent(model_name: str = DEFAULT_MODEL):
    """Create the agent. Built on demand so importing this file never
    needs an API key or blocks on input."""
    model = ChatGoogleGenerativeAI(model=model_name)
    return create_agent(model=model, tools=TOOLS, system_prompt=SYSTEM_PROMPT)


def message_text(content) -> str:
    """Gemini can return a list of content blocks; keep only the text."""
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return content or ""


# Terminal chat: only runs with `python agent.py`, never when app.py imports it.
if __name__ == "__main__":
    agent = build_agent()
    messages = []
    print("City assistant. Type exit to quit.\n")
    while True:
        user_input = input("you: ").strip()
        if user_input.lower() == "exit":
            break
        messages.append({"role": "user", "content": user_input})
        messages = messages[-6:]  # Keep only recent conversation
        result = agent.invoke({"messages": messages})
        messages = [
            {"role": "user" if m.type == "human" else "assistant", "content": message_text(m.content)}
            for m in result["messages"]
            if m.type in ("human", "ai") and message_text(m.content).strip()
        ]
        print(f"\nAI: {messages[-1]['content']}\n")